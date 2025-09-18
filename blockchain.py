# blockchain.py
import hashlib
import json
import time
import requests
from wallet import Wallet
import os

MINING_REWARD = 100
FAUCET_REWARD = 100

class Blockchain:
    def __init__(self, port, notary_public_key):
        self.chain = []
        self.pending_transactions = []
        self.nodes = set()
        self.port = port
        self.notary_public_key = notary_public_key

        self.blockchain_dir = "data/blockchain"
        os.makedirs(self.blockchain_dir, exist_ok=True)
        self.chain_file = os.path.join(self.blockchain_dir, f'blockchain_{self.port}.json')

        self.state = {
            'balances': {},
            'tokens': {},
            'contracts': {}
        }

        self.load_chain_and_rebuild_state()

        if not self.chain:
            self.create_block(previous_hash='0', proof=100)

    def rebuild_state_from_chain(self):
        self.state = {'balances': {}, 'tokens': {}, 'contracts': {}}
        for block in self.chain:
            for tx_data in block['transactions']:
                self._process_transaction_for_state_update(tx_data)

    def _process_transaction_for_state_update(self, tx_data):
        tx = tx_data['transaction']
        tx_type = tx['data'].get('type')
        payload = tx['data'].get('payload', {})
        sender = tx['sender']
        recipient = tx['recipient']
        sender_balance = self.state['balances'].get(sender, 0)
        recipient_balance = self.state['balances'].get(recipient, 0)

        if sender == "0":
            reward = MINING_REWARD if tx_type == 'MINING_REWARD' else FAUCET_REWARD
            self.state['balances'][recipient] = recipient_balance + reward
            return
            
        if tx_type == 'MINT_TOKEN':
            if sender != self.notary_public_key: return
            token_id = payload.get('token_id')
            if token_id not in self.state['tokens']:
                self.state['tokens'][token_id] = recipient
        
        elif tx_type == 'TRANSFER_CURRENCY':
            amount = payload.get('amount')
            if sender_balance >= amount:
                self.state['balances'][sender] = sender_balance - amount
                self.state['balances'][recipient] = recipient_balance + amount
        
        elif tx_type == 'CREATE_SALE_CONTRACT':
            payload = tx['data'].get('payload', {})
            token_id = payload.get('token_id')
            if token_id in self.state['tokens'] and self.state['tokens'][token_id] == sender:
                self.state['contracts'][payload.get('contract_id')] = {
                    'token_id': token_id, 'seller': sender, 'price': payload.get('price'),
                    'conditions': payload.get('conditions'), 'valid_until': payload.get('valid_until'), 'status': 'OPEN'
                }
        elif tx_type == 'EXECUTE_SALE_CONTRACT':
            contract_id = payload.get('contract_id')
            contract = self.state['contracts'].get(contract_id)
            buyer = sender
            if not (contract and contract['status'] == 'OPEN'): return
            if time.time() > contract.get('valid_until', float('inf')):
                self.state['contracts'][contract_id]['status'] = 'EXPIRED'
                return
            price = contract['price']
            if sender_balance < price: return
            seller = contract['seller']
            token_id = contract['token_id']
            self.state['balances'][buyer] = sender_balance - price
            self.state['balances'][seller] = self.state['balances'].get(seller, 0) + price
            self.state['tokens'][token_id] = buyer
            self.state['contracts'][contract_id]['status'] = 'CLOSED'
            self.state['contracts'][contract_id]['buyer'] = buyer

    def save_chain(self):
        with open(self.chain_file, 'w') as f: json.dump(self.chain, f, indent=4)

    def load_chain_and_rebuild_state(self):
        try:
            with open(self.chain_file, 'r') as f: self.chain = json.load(f)
            self.rebuild_state_from_chain()
        except (FileNotFoundError, json.JSONDecodeError): self.chain = []

    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain) + 1, 'timestamp': time.time(),
            'transactions': self.pending_transactions, 'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        for tx in self.pending_transactions:
            self._process_transaction_for_state_update(tx)
        self.pending_transactions = []
        self.chain.append(block)
        self.save_chain()
        return block

    def add_block(self, block):
        last_block = self.last_block
        if (block['previous_hash'] != self.hash(last_block) or
            block['index'] != last_block['index'] + 1 or
            not self.valid_proof(last_block['proof'], block['proof'])):
            return False
        
        temp_chain = self.chain + [block]
        if self.is_chain_valid(temp_chain):
            self.chain.append(block)
            self.rebuild_state_from_chain()
            
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

    def add_transaction(self, sender_address, recipient_address, signature, data):
        transaction = {'sender': sender_address, 'recipient': recipient_address, 'data': data}
        if sender_address == "0":
            self.pending_transactions.append({'transaction': transaction, 'signature': 'reward'})
            return self.last_block['index'] + 1
        
        if Wallet.verify_transaction(sender_address, transaction, signature):
            if transaction['data'].get('type') == 'MINT_TOKEN' and sender_address != self.notary_public_key:
                return False
            self.pending_transactions.append({'transaction': transaction, 'signature': signature})
            return self.last_block['index'] + 1
        return False

    @staticmethod
    def hash(block):
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def hash_transaction(transaction):
        return hashlib.sha256(json.dumps(transaction, sort_keys=True).encode()).hexdigest()

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
            self.rebuild_state_from_chain()
            return True
        return False
        
    def is_chain_valid(self, chain):
        if not chain: return False
        last_block, current_index = chain[0], 1
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block) or \
               not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block, current_index = block, current_index + 1
        return True

    def get_token_history(self, token_id):
        history = []
        separator = "=" * 60
        
        for block in self.chain:
            for tx_data in block['transactions']:
                tx = tx_data['transaction']
                tx_type = tx['data'].get('type')
                payload = tx['data'].get('payload', {})
                
                current_tx_token_id = None
                
                if tx_type in ['MINT_TOKEN', 'CREATE_SALE_CONTRACT']:
                    current_tx_token_id = payload.get('token_id')
                elif tx_type == 'EXECUTE_SALE_CONTRACT':
                    contract_id = payload.get('contract_id')
                    original_contract = self._find_contract_in_history(contract_id)
                    if original_contract:
                        current_tx_token_id = original_contract.get('token_id')

                if current_tx_token_id == token_id:
                    tx_hash = self.hash_transaction(tx)
                    timestamp = time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(block['timestamp']))
                    
                    card = [separator]
                    
                    if tx_type == 'MINT_TOKEN':
                        owner_hash = hashlib.sha256(tx['recipient'].encode()).hexdigest()[:16]
                        card.append("EVENTO:         REGISTRO (MINT)")
                        card.append(f"TIMESTAMP:      {timestamp}")
                        card.append(f"BLOCO:          #{block['index']} ({self.hash(block)[:16]}...)")
                        card.append(f"HASH DA TX:     {tx_hash[:16]}...")
                        card.append("\nDETALHES:")
                        card.append(f"  - Ativo (Token ID): {token_id}")
                        card.append(f"  - Dono Inicial:     {owner_hash}")

                    elif tx_type == 'CREATE_SALE_CONTRACT':
                        seller_hash = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                        price = payload.get('price')
                        card.append("EVENTO:         OFERTA DE VENDA")
                        card.append(f"TIMESTAMP:      {timestamp}")
                        card.append(f"BLOCO:          #{block['index']} ({self.hash(block)[:16]}...)")
                        card.append(f"HASH DA TX:     {tx_hash[:16]}...")
                        card.append("\nDETALHES:")
                        card.append(f"  - Ativo (Token ID): {token_id}")
                        card.append(f"  - Vendedor:         {seller_hash}")
                        card.append(f"  - Preço:            {price} moedas")

                    elif tx_type == 'EXECUTE_SALE_CONTRACT':
                        original_contract = self._find_contract_in_history(payload.get('contract_id'))
                        if original_contract:
                            seller_hash = hashlib.sha256(original_contract['seller'].encode()).hexdigest()[:16]
                            buyer_hash = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                            price = original_contract['price']
                            card.append("EVENTO:         TRANSFERÊNCIA (VENDA CONCLUÍDA)")
                            card.append(f"TIMESTAMP:      {timestamp}")
                            card.append(f"BLOCO:          #{block['index']} ({self.hash(block)[:16]}...)")
                            card.append(f"HASH DA TX:     {tx_hash[:16]}...")
                            card.append("\nDETALHES:")
                            card.append(f"  - Ativo (Token ID):   {token_id}")
                            card.append(f"  - De (Vendedor):    {seller_hash}")
                            card.append(f"  - Para (Comprador): {buyer_hash}")
                            card.append(f"  - Valor:            {price} moedas")
                    
                    card.append(separator)
                    history.append("\n".join(card))
        
        return history

    def _find_contract_in_history(self, contract_id):
        for block in reversed(self.chain):
            for tx_data in block['transactions']:
                tx = tx_data['transaction']
                if tx['data'].get('type') == 'CREATE_SALE_CONTRACT':
                    payload = tx['data'].get('payload', {})
                    if payload.get('contract_id') == contract_id:
                        contract_data = payload.copy()
                        contract_data['seller'] = tx['sender']
                        return contract_data
        return None

    def get_balance(self, address):
        return self.state['balances'].get(address, 0)
    
    def get_owned_tokens(self, address):
        return [token for token, owner in self.state['tokens'].items() if owner == address]

    def get_contracts(self):
        return self.state['contracts']