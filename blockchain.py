# blockchain.py
import hashlib
import json
import os
import time

import requests

from wallet import Wallet

MINING_REWARD = 100
FAUCET_REWARD = 100
TAX_RATE = 0.05  # 5% de imposto (ITBI)
DIFFICULTY = "0000"  # prefixo exigido no hash de um bloco válido (Proof-of-Work)
# Gênesis fixo: todos os nós partem exatamente do mesmo bloco inicial.
GENESIS = {'index': 1, 'timestamp': 0, 'transactions': [], 'proof': 100, 'previous_hash': '0'}


class Blockchain:
    def __init__(self, port, government_public_key, tax_authority_public_key):
        self.pending_transactions = []
        self.nodes = set()
        self.port = port
        self.government_public_key = government_public_key.strip()  # Chave do Governo
        self.tax_authority_public_key = tax_authority_public_key.strip()  # Chave da Receita

        self.blockchain_dir = "data/blockchain"
        os.makedirs(self.blockchain_dir, exist_ok=True)
        self.chain_file = os.path.join(self.blockchain_dir, f'blockchain_{self.port}.json')

        self.chain = self._load_chain()
        self.rebuild_state_from_chain()

    # --- Estado (derivado da cadeia) ---

    def rebuild_state_from_chain(self):
        self.state = {
            'balances': {},
            'tokens': {},
            'contracts': {},
            'authorized_notaries': set(),
            'certified_identities': set(),
            'notary_locations': {},
            'token_metadata': {},       # {token_id: {locality, asset_type, area, details_hash, ...}}
            'pending_sale_requests': {},
            'tax_receipts': []
        }
        for block in self.chain:
            self._apply_block(block)

    def _apply_block(self, block):
        for tx_data in block['transactions']:
            self._process_transaction_for_state_update(tx_data, block)

    def _process_transaction_for_state_update(self, tx_data, block):
        # Regras de consenso: dependem só da cadeia (nunca do relógio local),
        # para que todo nó chegue ao mesmo estado ao reprocessar os blocos.
        tx = tx_data['transaction']
        tx_type = tx['data'].get('type')
        payload = tx['data'].get('payload', {})
        sender = tx['sender'].strip()
        recipient = tx['recipient'].strip()

        sender_balance = self.state['balances'].get(sender, 0)
        recipient_balance = self.state['balances'].get(recipient, 0)

        if sender == "0":
            reward = MINING_REWARD if tx_type == 'MINING_REWARD' else FAUCET_REWARD
            self.state['balances'][recipient] = recipient_balance + reward
            return

        if tx_type == 'MINT_TOKEN':
            if sender in self.state['authorized_notaries']:
                token_id = payload.get('token_id')
                locality = payload.get('locality')
                asset_type = payload.get('asset_type')
                area = payload.get('area')
                details_hash = payload.get('details_hash')

                if token_id and locality and asset_type and area and details_hash and (token_id not in self.state['tokens']):
                    self.state['tokens'][token_id] = recipient  # recipient é o primeiro dono
                    self.state['token_metadata'][token_id] = {
                        'locality': locality,
                        'asset_type': asset_type,
                        'area': area,
                        'details_hash': details_hash,
                        'minted_by': sender,
                        'gov_issues': False,
                        'paid_off': True
                    }
                    print(f"[State Update] Ativo {token_id} mintado em {locality}.")
            else:
                print(f"[State Update] Falha no MINT: Remetente {sender[:10]}... não é um cartório autorizado.")

        elif tx_type == 'TRANSFER_CURRENCY':
            amount = payload.get('amount')
            if isinstance(amount, int) and 0 < amount <= sender_balance:
                self.state['balances'][sender] = sender_balance - amount
                self.state['balances'][recipient] = recipient_balance + amount

        elif tx_type == 'REGISTER_NOTARY':
            if sender == self.government_public_key:
                notary_pk = recipient
                locality = payload.get('locality')
                if notary_pk and locality:
                    self.state['authorized_notaries'].add(notary_pk)
                    self.state['notary_locations'][notary_pk] = locality
                    print(f"[State Update] Cartório {notary_pk[:10]}... adicionado em {locality}.")
            else:
                print("[State Update] Falha ao registrar cartório: Remetente não é o governo.")

        elif tx_type == 'CERTIFY_IDENTITY':
            if sender in self.state['authorized_notaries']:
                self.state['certified_identities'].add(recipient)
                print(f"[State Update] Identidade {recipient[:10]}... certificada por {sender[:10]}.")

        elif tx_type == 'REQUEST_SALE_APPROVAL':
            token_id = payload.get('token_id')
            request_id = payload.get('request_id')
            price = payload.get('price')
            if (self.state['tokens'].get(token_id) == sender and request_id
                    and request_id not in self.state['pending_sale_requests']
                    and isinstance(price, int) and price > 0):
                token_locality = self.state['token_metadata'].get(token_id, {}).get('locality')
                if token_locality:
                    self.state['pending_sale_requests'][request_id] = {
                        'token_id': token_id,
                        'seller': sender,
                        'price': price,
                        'status': 'PENDING',
                        'locality': token_locality
                    }
                    print(f"[State Update] Solicitação de Venda {request_id[:8]}... criada para {token_id} em {token_locality}.")

        elif tx_type == 'APPROVE_SALE':
            if sender in self.state['authorized_notaries']:
                request_id = payload.get('request_id')
                request = self.state['pending_sale_requests'].get(request_id)
                contract_id = payload.get('contract_id')
                notary_locality = self.state['notary_locations'].get(sender)
                if (request and request['status'] == 'PENDING' and request['locality'] == notary_locality
                        and contract_id and contract_id not in self.state['contracts']):
                    request['status'] = 'APPROVED'
                    self.state['contracts'][contract_id] = {
                        'token_id': request['token_id'],
                        'seller': request['seller'],
                        'price': request['price'],
                        'status': 'OPEN',
                        'valid_until': payload.get('valid_until'),
                        'approved_by': sender,
                        'original_request_id': request_id
                    }
                    print(f"[State Update] Venda {request_id[:8]}... APROVADA. Contrato {contract_id[:8]}... criado.")

        elif tx_type == 'REJECT_SALE':
            if sender in self.state['authorized_notaries']:
                request_id = payload.get('request_id')
                request = self.state['pending_sale_requests'].get(request_id)
                notary_locality = self.state['notary_locations'].get(sender)
                if request and request['status'] == 'PENDING' and request['locality'] == notary_locality:
                    request['status'] = 'REJECTED'
                    request['reason'] = payload.get('reason')
                    request['rejected_by'] = sender
                    print(f"[State Update] Venda {request_id[:8]}... REJEITADA. Motivo: {payload.get('reason')}")

        elif tx_type == 'EXECUTE_SALE_CONTRACT':
            contract_id = payload.get('contract_id')
            contract = self.state['contracts'].get(contract_id)
            buyer = sender

            if not (contract and contract['status'] == 'OPEN'):
                return
            # A validade é comparada com o horário do BLOCO, não com o relógio atual:
            # assim a venda continua válida quando a cadeia é reprocessada no futuro.
            if (contract.get('valid_until') or float('inf')) < block['timestamp']:
                contract['status'] = 'EXPIRED'
                return

            price = contract['price']
            seller = contract['seller']
            token_id = contract['token_id']
            if self.state['tokens'].get(token_id) != seller:
                contract['status'] = 'CANCELLED'  # o vendedor não é mais o dono do ativo
                return
            tax = int(price * TAX_RATE)
            total_cost = price + tax

            if sender_balance < total_cost:
                print(f"[State Update] Falha na Venda: Saldo insuficiente. Precisa de {total_cost}, tem {sender_balance}")
                return

            # Contrato atômico: pagamento, imposto e transferência do ativo na mesma transação.
            seller_balance = self.state['balances'].get(seller, 0)
            tax_auth_balance = self.state['balances'].get(self.tax_authority_public_key, 0)

            self.state['balances'][buyer] = sender_balance - total_cost
            self.state['balances'][seller] = seller_balance + price
            self.state['balances'][self.tax_authority_public_key] = tax_auth_balance + tax
            self.state['tokens'][token_id] = buyer
            contract['status'] = 'CLOSED'
            contract['buyer'] = buyer

            self.state['tax_receipts'].append({
                'receipt_id': hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest(),
                'timestamp': block['timestamp'],
                'block_index': block['index'],
                'token_id': token_id,
                'buyer': buyer,
                'seller': seller,
                'price': price,
                'tax_paid': tax,
                'tax_authority_recipient': self.tax_authority_public_key
            })
            print(f"[State Update] Venda Concluída. Token {token_id} transferido para {buyer[:10]}...")
            print(f"[State Update] Imposto de {tax} moedas pago para {self.tax_authority_public_key[:10]}...")

    # --- Persistência ---

    def save_chain(self):
        try:
            with open(self.chain_file, 'w') as f:
                json.dump(self.chain, f, indent=4)
        except OSError as e:
            print(f"Erro ao salvar {self.chain_file}: {e}")

    def _load_chain(self):
        try:
            with open(self.chain_file, 'r') as f:
                chain = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return [dict(GENESIS)]
        if self.is_chain_valid(chain):
            return chain
        # Arquivo editado à mão (ou de uma versão antiga): a cadeia é refeita a partir da rede.
        print(f"[Load] {self.chain_file} é inválido (adulterado?). Recomeçando do bloco gênesis.")
        return [dict(GENESIS)]

    # --- Blocos e mineração ---

    @property
    def last_block(self):
        return self.chain[-1]

    def mine_block(self, miner_address):
        """Fecha um bloco com as transações pendentes + a recompensa do minerador."""
        self.add_transaction("0", miner_address, "reward", {'type': 'MINING_REWARD'})
        block = {
            'index': self.last_block['index'] + 1,
            'timestamp': max(time.time(), self.last_block['timestamp']),
            'transactions': self.pending_transactions,
            'previous_hash': self.hash(self.last_block),
            'proof': 0,
        }
        block['proof'] = self.proof_of_work(block)
        self.pending_transactions = []
        self.chain.append(block)
        self._apply_block(block)
        self.save_chain()
        return block

    def add_block(self, block):
        """Recebe um bloco minerado por outro nó."""
        if not self._is_valid_next(self.last_block, block):
            print(f"[Add Block] Bloco #{block.get('index')} rejeitado: encadeamento, PoW ou assinatura inválidos.")
            return False

        self.chain.append(block)
        self._apply_block(block)
        received_tx_ids = {json.dumps(tx['transaction'], sort_keys=True) for tx in block['transactions']}
        self.pending_transactions = [
            ptx for ptx in self.pending_transactions
            if json.dumps(ptx['transaction'], sort_keys=True) not in received_tx_ids
        ]
        self.save_chain()
        print(f"[Add Block] Bloco #{block['index']} aceito.")
        return True

    def add_transaction(self, sender_address, recipient_address, signature, data):
        sender_address = sender_address.strip()
        recipient_address = recipient_address.strip()

        transaction = {'sender': sender_address, 'recipient': recipient_address, 'data': data}

        if sender_address == "0":
            self.pending_transactions.append({'transaction': transaction, 'signature': 'reward'})
            return self.last_block['index'] + 1

        if Wallet.verify_transaction(sender_address, transaction, signature):
            tx_type = transaction['data'].get('type')

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
                    print("[Add TX Error] Falha na APROVAÇÃO/REJEIÇÃO: Remetente não é um cartório.")
                    return False
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

    # --- Hash, Proof-of-Work e validação ---

    @staticmethod
    def _header_hash(block):
        """Hash de todo o conteúdo do bloco, exceto a prova."""
        header = {k: v for k, v in block.items() if k != 'proof'}
        return hashlib.sha256(json.dumps(header, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _pow_hash(header_hash, proof):
        return hashlib.sha256(f'{header_hash}{proof}'.encode()).hexdigest()

    @classmethod
    def hash(cls, block):
        # A prova cobre o conteúdo inteiro: alterar qualquer transação invalida o PoW
        # deste bloco e o previous_hash de todos os seguintes.
        return cls._pow_hash(cls._header_hash(block), block['proof'])

    @classmethod
    def proof_of_work(cls, block):
        header_hash = cls._header_hash(block)
        proof = 0
        while not cls._pow_hash(header_hash, proof).startswith(DIFFICULTY):
            proof += 1
        return proof

    @classmethod
    def valid_proof(cls, block):
        return cls.hash(block).startswith(DIFFICULTY)

    def _is_valid_next(self, prev, block):
        """Bloco encadeado em prev, com PoW válido e todas as transações assinadas pelo remetente."""
        try:
            return (block['index'] == prev['index'] + 1
                    and block['previous_hash'] == self.hash(prev)
                    and block['timestamp'] >= prev['timestamp']
                    and self.valid_proof(block)
                    and all(self._is_signed(tx) for tx in block['transactions']))
        except (KeyError, TypeError, AttributeError):
            return False  # bloco malformado vindo da rede

    @staticmethod
    def _is_signed(tx_data):
        tx = tx_data['transaction']
        return tx['sender'] == "0" or Wallet.verify_transaction(tx['sender'], tx, tx_data['signature'])

    def is_chain_valid(self, chain):
        return (isinstance(chain, list) and bool(chain) and chain[0] == GENESIS
                and all(self._is_valid_next(prev, block) for prev, block in zip(chain, chain[1:])))

    # --- Rede ---

    def add_node(self, address):
        self.nodes.add(address)

    def resolve_conflicts(self):
        """Consenso: adota a maior cadeia VÁLIDA entre os vizinhos."""
        new_chain, max_length = None, len(self.chain)
        for node in self.nodes:
            try:
                response = requests.get(f'http://{node}/chain', timeout=2)
                if response.status_code == 200:
                    chain = response.json()['chain']
                    if len(chain) > max_length and self.is_chain_valid(chain):
                        max_length, new_chain = len(chain), chain
            except (requests.exceptions.RequestException, ValueError, KeyError):
                continue
        if new_chain:
            self.chain = new_chain
            self.save_chain()
            self.rebuild_state_from_chain()
            return True
        return False

    # --- Consultas ---

    def get_token_history(self, token_id):
        history = []
        separator = "=" * 60
        contracts = self.state['contracts']
        requests_ = self.state['pending_sale_requests']
        short = lambda key: hashlib.sha256(key.encode()).hexdigest()[:16]
        for block in self.chain:
            for tx_data in block['transactions']:
                tx = tx_data['transaction']
                tx_type = tx['data'].get('type')
                payload = tx['data'].get('payload', {})
                if tx_type in ('MINT_TOKEN', 'REQUEST_SALE_APPROVAL'):
                    tx_token_id = payload.get('token_id')
                elif tx_type in ('APPROVE_SALE', 'REJECT_SALE'):
                    tx_token_id = requests_.get(payload.get('request_id'), {}).get('token_id')
                elif tx_type == 'EXECUTE_SALE_CONTRACT':
                    tx_token_id = contracts.get(payload.get('contract_id'), {}).get('token_id')
                else:
                    continue
                if tx_token_id != token_id:
                    continue

                timestamp = time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(block['timestamp']))
                when = f"TIMESTAMP:      {timestamp} (Bloco #{block['index']})"
                card = [separator]
                if tx_type == 'MINT_TOKEN':
                    card += [f"EVENTO:         REGISTRO (MINT) EM {payload.get('locality')}", when,
                             f"  - Ativo (Token ID): {token_id}",
                             f"  - Dono Inicial:     {short(tx['recipient'])}",
                             f"  - Cartório (Emissor): {short(tx['sender'])}",
                             f"  - Hash Detalhes:    {payload.get('details_hash', 'N/A')[:16]}..."]
                elif tx_type == 'REQUEST_SALE_APPROVAL':
                    card += ["EVENTO:         SOLICITAÇÃO DE VENDA", when,
                             f"  - Vendedor:         {short(tx['sender'])}",
                             f"  - Preço Sugerido:   {payload.get('price')} moedas"]
                elif tx_type == 'APPROVE_SALE':
                    card += ["EVENTO:         VENDA APROVADA (CONTRATO CRIADO)", when,
                             f"  - Cartório:         {short(tx['sender'])}",
                             f"  - Contrato ID:      {payload.get('contract_id', 'N/A')[:16]}..."]
                elif tx_type == 'REJECT_SALE':
                    card += ["EVENTO:         VENDA REJEITADA", when,
                             f"  - Cartório:         {short(tx['sender'])}",
                             f"  - Motivo:           {payload.get('reason', 'N/A')}"]
                else:  # EXECUTE_SALE_CONTRACT
                    contract = contracts[payload.get('contract_id')]
                    if contract.get('buyer') != tx['sender'].strip():
                        continue  # tentativa de compra que não se concretizou
                    card += ["EVENTO:         TRANSFERÊNCIA (VENDA CONCLUÍDA)", when,
                             f"  - De (Vendedor):    {short(contract['seller'])}",
                             f"  - Para (Comprador): {short(tx['sender'])}",
                             f"  - Valor:            {contract['price']} moedas",
                             f"  - Imposto (ITBI):   {int(contract['price'] * TAX_RATE)} moedas"]
                card.append(separator)
                history.append("\n".join(card))
        return history

    def get_balance(self, address):
        return self.state['balances'].get(address.strip(), 0)

    def get_owned_tokens(self, address):
        address = address.strip()
        return [token for token, owner in self.state['tokens'].items() if owner == address]

    def get_contracts(self):
        """Contratos à venda: abertos e dentro da validade."""
        now = time.time()
        return {cid: data for cid, data in self.state['contracts'].items()
                if data['status'] == 'OPEN' and (data.get('valid_until') or float('inf')) > now}

    def get_notary_locality(self, notary_pk):
        return self.state['notary_locations'].get(notary_pk.strip())

    def get_token_metadata(self, token_id):
        return self.state['token_metadata'].get(token_id, {})

    def get_pending_sale_requests(self, locality):
        return [dict(data, request_id=req_id) for req_id, data in self.state['pending_sale_requests'].items()
                if data['status'] == 'PENDING' and data['locality'] == locality]

    def get_tax_receipts(self, user_pk):
        user_pk = user_pk.strip()
        return [receipt for receipt in self.state['tax_receipts'] if receipt['buyer'] == user_pk]

    def get_my_token_status(self, token_id):
        if any(c['token_id'] == token_id for c in self.get_contracts().values()):
            return "À Venda (Aprovado)"
        owner = self.state['tokens'].get(token_id)
        my_requests = [r for r in self.state['pending_sale_requests'].values()
                       if r['token_id'] == token_id and r['seller'] == owner]
        if any(r['status'] == 'PENDING' for r in my_requests):
            return "Pendente de Aprovação"
        if my_requests and my_requests[-1]['status'] == 'REJECTED':
            reason = my_requests[-1].get('reason') or 'N/A'
            return f"Em Carteira (venda recusada: {reason[:30]}{'...' if len(reason) > 30 else ''})"
        return "Em Carteira"
