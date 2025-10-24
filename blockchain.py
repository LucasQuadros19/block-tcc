# blockchain.py
import hashlib
import json
import time
import requests
from wallet import Wallet
import os

MINING_REWARD = 100
FAUCET_REWARD = 100
TAX_RATE = 0.05 # 5% de imposto (ITBI)

class Blockchain:
    def __init__(self, port, government_public_key, tax_authority_public_key):
        self.chain = []
        self.pending_transactions = []
        self.nodes = set()
        self.port = port
        self.government_public_key = government_public_key # Chave do Governo
        self.tax_authority_public_key = tax_authority_public_key # Chave da Receita

        self.blockchain_dir = "data/blockchain"
        os.makedirs(self.blockchain_dir, exist_ok=True)
        self.chain_file = os.path.join(self.blockchain_dir, f'blockchain_{self.port}.json')

        self.state = {
            'balances': {},
            'tokens': {},
            'contracts': {},
            'authorized_notaries': set(),
            'certified_identities': set(),
            'notary_locations': {},
            # ATUALIZADO: 'details' virou 'details_hash'
            'token_metadata': {},       # {token_id: {locality: "...", details_hash: "...", ...}}
            'pending_sale_requests': {},
            'tax_receipts': []
        }

        self.load_chain_and_rebuild_state()

        if not self.chain:
            self.create_block(previous_hash='0', proof=100)

    def rebuild_state_from_chain(self):
        # ATUALIZADO: Limpa o estado completo
        self.state = {
            'balances': {},
            'tokens': {},
            'contracts': {},
            'authorized_notaries': set(),
            'certified_identities': set(),
            'notary_locations': {},
            'token_metadata': {},
            'pending_sale_requests': {},
            'tax_receipts': []
        }
        for block in self.chain:
            for tx_data in block['transactions']:
                self._process_transaction_for_state_update(tx_data)

    def _process_transaction_for_state_update(self, tx_data):
        tx = tx_data['transaction']
        tx_type = tx['data'].get('type')
        payload = tx['data'].get('payload', {})
        sender = tx['sender']
        recipient = tx['recipient']

        # Balanços (usados em várias transações)
        sender_balance = self.state['balances'].get(sender, 0)
        recipient_balance = self.state['balances'].get(recipient, 0)

        # Transações do Sistema (Recompensas)
        if sender == "0":
            reward = MINING_REWARD if tx_type == 'MINING_REWARD' else FAUCET_REWARD
            self.state['balances'][recipient] = recipient_balance + reward
            return

        # Transações de Usuário
        if tx_type == 'TRANSFER_CURRENCY':
            amount = payload.get('amount')
            if sender_balance >= amount:
                self.state['balances'][sender] = sender_balance - amount
                self.state['balances'][recipient] = recipient_balance + amount

        # --- LÓGICA DE GOVERNANÇA E CARTÓRIO ---
        elif tx_type == 'REGISTER_NOTARY':
            # Sender deve ser o Governo
            if sender == self.government_public_key:
                notary_pk = recipient
                locality = payload.get('locality')
                if notary_pk and locality:
                    self.state['authorized_notaries'].add(notary_pk)
                    self.state['notary_locations'][notary_pk] = locality
                    print(f"[State Update] Cartório {notary_pk[:10]}... adicionado em {locality}.")
            else:
                print(f"[State Update] Falha ao registrar cartório: Remetente não é o governo.")

        elif tx_type == 'CERTIFY_IDENTITY':
            # Sender deve ser um cartório
            if sender in self.state['authorized_notaries']:
                self.state['certified_identities'].add(recipient)
                print(f"[State Update] Identidade {recipient[:10]}... certificada por {sender[:10]}.")

        elif tx_type == 'MINT_TOKEN':
            # Sender deve ser um cartório
            if sender in self.state['authorized_notaries']:
                token_id = payload.get('token_id')
                locality = payload.get('locality')
                details_hash = payload.get('details_hash') # ATUALIZADO
                if token_id and locality and details_hash and (token_id not in self.state['tokens']):
                    self.state['tokens'][token_id] = recipient # recipient é o primeiro dono
                    self.state['token_metadata'][token_id] = {
                        'locality': locality,
                        'details_hash': details_hash, # ATUALIZADO
                        'minted_by': sender,
                        'gov_issues': False, # Mock data
                        'paid_off': True     # Mock data
                    }
                    print(f"[State Update] Ativo {token_id} mintado em {locality}.")
            else:
                 print(f"[State Update] Falha no MINT: Remetente {sender[:10]}... não é um cartório autorizado.")

        # --- LÓGICA DE VENDA (NOVO FLUXO) ---
        elif tx_type == 'REQUEST_SALE_APPROVAL':
            # Sender deve ser o dono do token
            token_id = payload.get('token_id')
            if self.state['tokens'].get(token_id) == sender:
                request_id = payload.get('request_id')
                # Busca a localidade do token pelos metadados
                token_metadata = self.state.get('token_metadata', {}).get(token_id, {})
                token_locality = token_metadata.get('locality')
                if request_id and token_locality:
                    self.state['pending_sale_requests'][request_id] = {
                        'token_id': token_id,
                        'seller': sender,
                        'price': payload.get('price'),
                        'status': 'PENDING',
                        'locality': token_locality # Adiciona a localidade à requisição
                    }
                    print(f"[State Update] Solicitação de Venda {request_id[:8]}... criada para {token_id} em {token_locality}.")

        elif tx_type == 'APPROVE_SALE':
            # Sender deve ser um cartório
            if sender in self.state['authorized_notaries']:
                request_id = payload.get('request_id')
                request = self.state['pending_sale_requests'].get(request_id)

                # Cartório só pode aprovar vendas da sua localidade
                notary_locality = self.state['notary_locations'].get(sender)
                if request and request['status'] == 'PENDING' and request['locality'] == notary_locality:
                    request['status'] = 'APPROVED' # Marca a requisição como aprovada
                    contract_id = payload.get('contract_id')
                    # Cria o contrato de venda no estado
                    self.state['contracts'][contract_id] = {
                        'token_id': request['token_id'],
                        'seller': request['seller'],
                        'price': request['price'],
                        'status': 'OPEN', # Contrato fica aberto para compra
                        'valid_until': payload.get('valid_until'),
                        'approved_by': sender,
                        'original_request_id': request_id
                    }
                    print(f"[State Update] Venda {request_id[:8]}... APROVADA. Contrato {contract_id[:8]}... criado.")

        elif tx_type == 'REJECT_SALE':
             # Sender deve ser um cartório
            if sender in self.state['authorized_notaries']:
                request_id = payload.get('request_id')
                request = self.state['pending_sale_requests'].get(request_id)

                notary_locality = self.state['notary_locations'].get(sender)
                if request and request['status'] == 'PENDING' and request['locality'] == notary_locality:
                    request['status'] = 'REJECTED' # Marca como rejeitada
                    request['reason'] = payload.get('reason')
                    request['rejected_by'] = sender
                    print(f"[State Update] Venda {request_id[:8]}... REJEITADA. Motivo: {payload.get('reason')}")

        elif tx_type == 'EXECUTE_SALE_CONTRACT':
            # Lógica de compra com imposto
            contract_id = payload.get('contract_id')
            contract = self.state['contracts'].get(contract_id)
            buyer = sender # Buyer é o SENDER da transação

            if not (contract and contract['status'] == 'OPEN'): return
            if contract.get('valid_until', float('inf')) < time.time():
                self.state['contracts'][contract_id]['status'] = 'EXPIRED'
                return

            price = contract['price']
            seller = contract['seller']
            token_id = contract['token_id']

            # Cálculo de Imposto
            tax = int(price * TAX_RATE) # Usar int para evitar floats
            total_cost = price + tax

            if sender_balance < total_cost:
                print(f"[State Update] Falha na Venda: Saldo insuficiente. Precisa de {total_cost}, tem {sender_balance}")
                return

            # Obter balanços do vendedor e da autoridade fiscal
            seller_balance = self.state['balances'].get(seller, 0)
            tax_auth_balance = self.state['balances'].get(self.tax_authority_public_key, 0)

            # 1. Paga Vendedor e Imposto
            self.state['balances'][buyer] = sender_balance - total_cost
            self.state['balances'][seller] = seller_balance + price
            self.state['balances'][self.tax_authority_public_key] = tax_auth_balance + tax

            # 2. Transfere o Token
            self.state['tokens'][token_id] = buyer

            # 3. Fecha o Contrato
            self.state['contracts'][contract_id]['status'] = 'CLOSED'
            self.state['contracts'][contract_id]['buyer'] = buyer

            # 4. CRIA O RECIBO DE IMPOSTO (A "CERTIDÃO")
            receipt = {
                'receipt_id': hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest(),
                'timestamp': time.time(),
                'block_index': len(self.chain) + 1, # Próximo bloco
                'token_id': token_id,
                'buyer': buyer,
                'seller': seller,
                'price': price,
                'tax_paid': tax,
                'tax_authority_recipient': self.tax_authority_public_key
            }
            self.state['tax_receipts'].append(receipt)

            print(f"[State Update] Venda Concluída. Token {token_id} transferido para {buyer[:10]}...")
            print(f"[State Update] Imposto de {tax} moedas pago para {self.tax_authority_public_key[:10]}...")

    # --- Funções de Save/Load/Chain ---
    # ... (sem alterações significativas, apenas garantindo conversão de sets) ...

    def save_chain(self):
        # Converte SETs para LISTs para serialização JSON
        chain_to_save = []
        for block in self.chain:
            block_copy = block.copy()
            chain_to_save.append(block_copy)

        try:
            with open(self.chain_file, 'w') as f:
                json.dump(chain_to_save, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar chain.json: {e}")

    def load_chain_and_rebuild_state(self):
        try:
            with open(self.chain_file, 'r') as f: self.chain = json.load(f)
            self.rebuild_state_from_chain()

            # Converte listas de volta para SETs após reconstruir
            self.state['authorized_notaries'] = set(self.state.get('authorized_notaries', []))
            self.state['certified_identities'] = set(self.state.get('certified_identities', []))

        except (FileNotFoundError, json.JSONDecodeError):
            self.chain = []

    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain) + 1, 'timestamp': time.time(),
            'transactions': self.pending_transactions, 'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        # Processa transações ANTES de limpar
        for tx in self.pending_transactions:
            self._process_transaction_for_state_update(tx)

        self.pending_transactions = []
        self.chain.append(block)
        self.save_chain() # Salva a cadeia

        # Garante que sets estejam corretos após processar transações do bloco
        self.state['authorized_notaries'] = set(self.state.get('authorized_notaries', []))
        self.state['certified_identities'] = set(self.state.get('certified_identities', []))

        return block

    def add_block(self, block):
        last_block = self.last_block
        if (block['previous_hash'] != self.hash(last_block) or
            block['index'] != last_block['index'] + 1 or
            not self.valid_proof(last_block['proof'], block['proof'])):
            return False

        temp_chain = self.chain + [block]
        if self.is_chain_valid(temp_chain):
            # Recalcula o estado com base na nova cadeia (mais seguro)
            self.chain = temp_chain
            self.rebuild_state_from_chain()

            # Converte listas de volta para SETs após reconstruir
            self.state['authorized_notaries'] = set(self.state.get('authorized_notaries', []))
            self.state['certified_identities'] = set(self.state.get('certified_identities', []))

            received_tx_ids = {json.dumps(tx['transaction'], sort_keys=True) for tx in block.get('transactions', [])}
            self.pending_transactions = [
                ptx for ptx in self.pending_transactions
                if json.dumps(ptx['transaction'], sort_keys=True) not in received_tx_ids
            ]
            self.save_chain()
            return True
        return False

    @property
    def last_block(self):
        return self.chain[-1]

    # --- Funções de Transação e Validação ---
    # ... (sem alterações significativas, as validações já estavam lá) ...

    def add_transaction(self, sender_address, recipient_address, signature, data):
        transaction = {'sender': sender_address, 'recipient': recipient_address, 'data': data}
        if sender_address == "0":
            self.pending_transactions.append({'transaction': transaction, 'signature': 'reward'})
            return self.last_block['index'] + 1

        if Wallet.verify_transaction(sender_address, transaction, signature):
            tx_type = transaction['data'].get('type')

            # --- Validações de Permissão ---
            if tx_type == 'MINT_TOKEN' and sender_address not in self.state['authorized_notaries']:
                 print(f"[Add TX Error] Falha no MINT: Remetente {sender_address[:10]}... não é um cartório autorizado.")
                 return False

            if tx_type == 'REGISTER_NOTARY' and sender_address != self.government_public_key:
                 print(f"[Add TX Error] Falha no REGISTRO: Remetente {sender_address[:10]}... não é o governo.")
                 return False

            if tx_type == 'CERTIFY_IDENTITY' and sender_address not in self.state['authorized_notaries']:
                 print(f"[Add TX Error] Falha na CERTIFICAÇÃO: Remetente {sender_address[:10]}... não é um cartório.")
                 return False

            if tx_type == 'REQUEST_SALE_APPROVAL':
                token_id = data.get('payload', {}).get('token_id')
                if self.state['tokens'].get(token_id) != sender_address:
                    print(f"[Add TX Error] Falha na SOLICITAÇÃO: Remetente não é o dono do token {token_id}.")
                    return False

            if tx_type in ['APPROVE_SALE', 'REJECT_SALE']:
                if sender_address not in self.state['authorized_notaries']:
                    print(f"[Add TX Error] Falha na APROVAÇÃO/REJEIÇÃO: Remetente não é um cartório.")
                    return False
                # Validação de localidade (comparando com a localidade da *requisição*)
                request_id = data.get('payload', {}).get('request_id')
                request = self.state['pending_sale_requests'].get(request_id)
                notary_locality = self.state['notary_locations'].get(sender_address)
                if not request:
                    print(f"[Add TX Error] Falha na APROVAÇÃO/REJEIÇÃO: Request ID {request_id} não encontrado.")
                    return False
                if request.get('locality') != notary_locality:
                    print(f"[Add TX Error] Falha na APROVAÇÃO/REJEIÇÃO: Cartório {sender_address[:10]} ({notary_locality}) não é da localidade da requisição ({request.get('locality')}).")
                    return False

            self.pending_transactions.append({'transaction': transaction, 'signature': signature})
            return self.last_block['index'] + 1

        print("[Add TX Error] Verificação de assinatura falhou.")
        return False

    @staticmethod
    def hash(block):
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def hash_transaction(transaction):
        return hashlib.sha256(json.dumps(transaction, sort_keys=True).encode()).hexdigest()

    # --- Funções PoW e Rede ---
    # ... (sem alterações) ...

    def proof_of_work(self, last_proof):
        proof = 0
        while not self.valid_proof(last_proof, proof): proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        guess_hash = hashlib.sha256(f'{last_proof}{proof}'.encode()).hexdigest()
        return guess_hash[:4] == "0000"

    def add_node(self, address):
        self.nodes.add(address)

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain, max_length = None, len(self.chain)
        for node in neighbours:
            try:
                response = requests.get(f'http://{node}/chain', timeout=2)
                if response.status_code == 200:
                    length, chain = response.json()['length'], response.json()['chain']
                    if length > max_length and self.is_chain_valid(chain):
                        max_length, new_chain = length, chain
            except requests.exceptions.RequestException: continue
        if new_chain:
            self.chain = new_chain
            self.save_chain()
            self.rebuild_state_from_chain() # Reconstrói o estado

            # Converte listas de volta para SETs após reconstruir
            self.state['authorized_notaries'] = set(self.state.get('authorized_notaries', []))
            self.state['certified_identities'] = set(self.state.get('certified_identities', []))
            return True
        return False

    def is_chain_valid(self, chain):
        if not chain: return False

        last_block, current_index = chain[0], 1

        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block) or \
               not self.valid_proof(last_block['proof'], block['proof']) or \
               block['index'] != last_block['index'] + 1:
                print(f"Validação falhou no bloco {block['index']}")
                return False
            last_block, current_index = block, current_index + 1
        return True

    # --- Funções Getters (Atualizadas/Novas) ---

    def get_token_history(self, token_id):
        history = []
        separator = "=" * 60

        for block in self.chain:
            for tx_data in block['transactions']:
                tx = tx_data['transaction']
                tx_type = tx['data'].get('type')
                payload = tx['data'].get('payload', {})

                current_tx_token_id = None

                # Identifica o token_id para cada tipo de transação relevante
                if tx_type == 'MINT_TOKEN':
                    current_tx_token_id = payload.get('token_id')
                elif tx_type == 'REQUEST_SALE_APPROVAL':
                    current_tx_token_id = payload.get('token_id')
                elif tx_type in ['APPROVE_SALE', 'REJECT_SALE']:
                    request_id = payload.get('request_id')
                    # Busca a solicitação original (pode ser lento se for muito antiga)
                    request = self._find_request_in_history(request_id)
                    if request: current_tx_token_id = request.get('token_id')
                elif tx_type == 'EXECUTE_SALE_CONTRACT':
                    contract_id = payload.get('contract_id')
                    # Busca o contrato original (pode ser lento)
                    original_contract = self._find_contract_in_history(contract_id)
                    if original_contract: current_tx_token_id = original_contract.get('token_id')


                if current_tx_token_id == token_id:
                    tx_hash = self.hash_transaction(tx)
                    timestamp = time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(block['timestamp']))
                    card = [separator]

                    if tx_type == 'MINT_TOKEN':
                        owner_hash = hashlib.sha256(tx['recipient'].encode()).hexdigest()[:16]
                        notary_hash = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                        card.append(f"EVENTO:         REGISTRO (MINT) EM {payload.get('locality')}")
                        card.append(f"TIMESTAMP:      {timestamp} (Bloco #{block['index']})")
                        card.append(f"  - Ativo (Token ID): {token_id}")
                        card.append(f"  - Dono Inicial:     {owner_hash}")
                        card.append(f"  - Cartório (Emissor): {notary_hash}")
                        # ATUALIZADO: Mostra o hash
                        card.append(f"  - Hash Detalhes:    {payload.get('details_hash', 'N/A')[:16]}...")

                    elif tx_type == 'REQUEST_SALE_APPROVAL':
                        seller_hash = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                        card.append(f"EVENTO:         SOLICITAÇÃO DE VENDA")
                        card.append(f"TIMESTAMP:      {timestamp} (Bloco #{block['index']})")
                        card.append(f"  - Vendedor:         {seller_hash}")
                        card.append(f"  - Preço Sugerido:   {payload.get('price')} moedas")

                    elif tx_type == 'APPROVE_SALE':
                        notary_hash = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                        card.append(f"EVENTO:         VENDA APROVADA (CONTRATO CRIADO)")
                        card.append(f"TIMESTAMP:      {timestamp} (Bloco #{block['index']})")
                        card.append(f"  - Cartório:         {notary_hash}")
                        card.append(f"  - Contrato ID:      {payload.get('contract_id', 'N/A')[:16]}...")

                    elif tx_type == 'REJECT_SALE':
                        notary_hash = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                        card.append(f"EVENTO:         VENDA REJEITADA")
                        card.append(f"TIMESTAMP:      {timestamp} (Bloco #{block['index']})")
                        card.append(f"  - Cartório:         {notary_hash}")
                        card.append(f"  - Motivo:           {payload.get('reason', 'N/A')}")

                    elif tx_type == 'EXECUTE_SALE_CONTRACT':
                        original_contract = self._find_contract_in_history(payload.get('contract_id'))
                        if original_contract:
                            seller_hash = hashlib.sha256(original_contract['seller'].encode()).hexdigest()[:16]
                            buyer_hash = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                            price = original_contract['price']
                            tax = int(price * TAX_RATE)
                            card.append(f"EVENTO:         TRANSFERÊNCIA (VENDA CONCLUÍDA)")
                            card.append(f"TIMESTAMP:      {timestamp} (Bloco #{block['index']})")
                            card.append(f"  - De (Vendedor):    {seller_hash}")
                            card.append(f"  - Para (Comprador): {buyer_hash}")
                            card.append(f"  - Valor:            {price} moedas")
                            card.append(f"  - Imposto (ITBI):   {tax} moedas")

                    card.append(separator)
                    history.append("\n".join(card))

        return history

    def _find_contract_in_history(self, contract_id):
        """Busca um contrato (mesmo fechado) pela história."""
        # Primeiro, checa o estado atual (pode estar aberto ou fechado)
        if contract_id in self.state['contracts']:
            return self.state['contracts'][contract_id]

        # Se não, busca na história pela transação de aprovação que o criou
        for block in reversed(self.chain):
            for tx_data in block['transactions']:
                tx = tx_data['transaction']
                if tx['data'].get('type') == 'APPROVE_SALE':
                    payload = tx['data'].get('payload', {})
                    if payload.get('contract_id') == contract_id:
                        # Reconstroi o contrato a partir da aprovação e da solicitação original
                        request_id = payload.get('original_request_id')
                        request = self._find_request_in_history(request_id)
                        if request:
                             return {
                                'token_id': request['token_id'],
                                'seller': request['seller'],
                                'price': request['price'],
                                'status': 'CLOSED', # Assumindo que foi fechado se não está mais no estado 'OPEN'
                                'approved_by': tx['sender'],
                                # Adiciona mais campos se necessário (buyer, etc.)
                            }
        return None

    def _find_request_in_history(self, request_id):
        """Busca uma solicitação de venda (mesmo processada) pela história."""
        # Checa o estado atual primeiro
        if request_id in self.state['pending_sale_requests']:
             return self.state['pending_sale_requests'][request_id]

        # Se não, busca na história pela transação que a criou
        for block in reversed(self.chain):
             for tx_data in block['transactions']:
                 tx = tx_data['transaction']
                 if tx['data'].get('type') == 'REQUEST_SALE_APPROVAL':
                     payload = tx['data'].get('payload', {})
                     if payload.get('request_id') == request_id:
                         # Recria o objeto da requisição
                         token_metadata = self.get_token_metadata(payload['token_id']) # Busca metadados
                         return {
                             'token_id': payload['token_id'],
                             'seller': tx['sender'],
                             'price': payload['price'],
                             'status': 'PROCESSED', # Não sabemos se foi APROVADO ou REJEITADO aqui
                             'locality': token_metadata.get('locality', 'N/A')
                         }
        return None

    def get_balance(self, address):
        return self.state['balances'].get(address, 0)

    def get_owned_tokens(self, address):
        return [token for token, owner in self.state['tokens'].items() if owner == address]

    def get_contracts(self):
        # Retorna apenas contratos ABERTOS
        return {cid: data for cid, data in self.state['contracts'].items() if data['status'] == 'OPEN'}

    # --- NOVOS GETTERS DE ESTADO ---

    def get_notary_locality(self, notary_pk):
        return self.state['notary_locations'].get(notary_pk)

    def get_token_metadata(self, token_id):
        return self.state['token_metadata'].get(token_id, {})

    def get_pending_sale_requests(self, locality):
        """Retorna todas as solicitações pendentes para uma dada localidade."""
        pending = []
        # LOG ADICIONADO
        print(f"[get_pending_sale_requests] Buscando para localidade: {locality}")
        found_in_state = 0
        for req_id, data in self.state['pending_sale_requests'].items():
            found_in_state +=1
            # LOG ADICIONADO
            # print(f"  - Verificando Req ID {req_id[:8]}... Status: {data['status']}, Localidade: {data['locality']}")
            if data['status'] == 'PENDING' and data['locality'] == locality:
                data_copy = data.copy()
                data_copy['request_id'] = req_id
                pending.append(data_copy)
        # LOG ADICIONADO
        print(f"[get_pending_sale_requests] Total de requests no estado: {found_in_state}. Encontrados {len(pending)} pendentes para {locality}.")
        return pending

    def get_tax_receipts(self, user_pk):
        """Retorna recibos onde o usuário foi o comprador."""
        my_receipts = []
        for receipt in self.state['tax_receipts']:
            if receipt['buyer'] == user_pk:
                my_receipts.append(receipt)
        return my_receipts

    def get_my_token_status(self, token_id):
        """Verifica o status de venda de um token (Pendente, Aprovado, etc)."""
        # 1. Está à venda (Contrato Aberto)?
        for contract in self.state['contracts'].values():
            if contract['token_id'] == token_id and contract['status'] == 'OPEN':
                return "À Venda (Aprovado)"

        # 2. Está pendente de aprovação ou foi rejeitado?
        for request in self.state['pending_sale_requests'].values():
            if request['token_id'] == token_id and request['status'] == 'PENDING':
                return "Pendente de Aprovação"
            if request['token_id'] == token_id and request['status'] == 'REJECTED':
                reason = request.get('reason', 'N/A')
                return f"Venda Rejeitada ({reason[:30]}{'...' if len(reason)>30 else ''})" # Limita tamanho da razão

        # 3. Se não, está apenas na carteira
        return "Em Carteira"

