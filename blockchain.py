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
    def __init__(self, port):
        self.chain = []
        self.pending_transactions = []
        self.nodes = set()
        self.port = port
        
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
        
        if tx_type == 'TRANSFER_CURRENCY':
            amount = payload.get('amount')
            if sender_balance >= amount:
                self.state['balances'][sender] = sender_balance - amount
                self.state['balances'][recipient] = recipient_balance + amount
        elif tx_type == 'MINT_TOKEN':
            token_id = payload.get('token_id')
            if token_id not in self.state['tokens']:
                self.state['tokens'][token_id] = recipient
        elif tx_type == 'CREATE_SALE_CONTRACT':
            contract_id = payload.get('contract_id')
            token_id = payload.get('token_id')
            price = payload.get('price')
            conditions = payload.get('conditions')
            valid_until = payload.get('valid_until')
            if token_id in self.state['tokens'] and self.state['tokens'][token_id] == sender:
                self.state['contracts'][contract_id] = {
                    'token_id': token_id, 
                    'seller': sender, 
                    'price': price, 
                    'conditions': conditions, 
                    'valid_until': valid_until, 
                    'status': 'OPEN'
                }
        elif tx_type == 'EXECUTE_SALE_CONTRACT':
            contract_id = payload.get('contract_id')
            contract = self.state['contracts'].get(contract_id)
            buyer = sender
            
            if not (contract and contract['status'] == 'OPEN'):
                print(f"Auditoria: Falha na compra. Contrato {contract_id[:8]} não está aberto.")
                return 

            if time.time() > contract['valid_until']:
                print(f"Auditoria: Falha na compra. Contrato {contract_id[:8]} expirou.")
                self.state['contracts'][contract_id]['status'] = 'EXPIRED'
                return

            price = contract['price']
            if sender_balance < price:
                print(f"Auditoria: Falha na compra. Saldo insuficiente.")
                return

            seller = contract['seller']
            token_id = contract['token_id']
            self.state['balances'][buyer] -= price
            self.state['balances'][seller] = self.state['balances'].get(seller, 0) + price
            self.state['tokens'][token_id] = buyer
            self.state['contracts'][contract_id]['status'] = 'CLOSED'
            self.state['contracts'][contract_id]['buyer'] = buyer
            print(f"Auditoria: Compra do contrato {contract_id[:8]} executada com sucesso.")

    def save_chain(self):
        with open(self.chain_file, 'w') as f:
            json.dump(self.chain, f, indent=4)

    def load_chain_and_rebuild_state(self):
        try:
            with open(self.chain_file, 'r') as f:
                self.chain = json.load(f)
            self.rebuild_state_from_chain()
        except (FileNotFoundError, json.JSONDecodeError):
            self.chain = []

    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.pending_transactions,
            'proof': proof,
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
        if block['previous_hash'] != self.hash(last_block):
            return False
        if not self.valid_proof(last_block['proof'], block['proof']):
            return False
        if not block['transactions']:
            return False
        
        self.pending_transactions = block['transactions']
        recreated_block = {
            'index': block['index'],
            'timestamp': block['timestamp'],
            'transactions': self.pending_transactions,
            'proof': block['proof'],
            'previous_hash': block['previous_hash'],
        }
        for tx in self.pending_transactions:
            self._process_transaction_for_state_update(tx)
        self.pending_transactions = []
        self.chain.append(recreated_block)
        self.save_chain()
        return True

    @property
    def last_block(self):
        return self.chain[-1]

    def add_transaction(self, sender_address, recipient_address, signature, data):
        transaction = {'sender': sender_address, 'recipient': recipient_address, 'data': data}
        if sender_address == "0":
            self.pending_transactions.append({'transaction': transaction, 'signature': 'reward'})
            return self.last_block['index'] + 1
        if Wallet.verify_transaction(sender_address, transaction, signature):
            self.pending_transactions.append({'transaction': transaction, 'signature': signature})
            return self.last_block['index'] + 1
        return False

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof):
        proof = 0
        while not self.valid_proof(last_proof, proof):
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"
    
    def add_node(self, address):
        self.nodes.add(address)

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)
        for node in neighbours:
            try:
                response = requests.get(f'http://{node}/chain')
                if response.status_code == 200:
                    length = response.json()['length']
                    chain = response.json()['chain']
                    if length > max_length:
                        max_length = length
                        new_chain = chain
            except requests.exceptions.RequestException:
                continue
        if new_chain:
            self.chain = new_chain
            self.save_chain()
            self.rebuild_state_from_chain()
            return True
        return False

    def get_token_history(self, token_id):
        history = []
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
                    contract = self.get_contracts().get(contract_id, {})
                    current_tx_token_id = contract.get('token_id')

                if current_tx_token_id == token_id:
                    entry = {
                        'block_index': block['index'],
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block['timestamp'])),
                        'event_type': tx_type,
                        'details': {}
                    }
                    if tx_type == 'MINT_TOKEN':
                        entry['details']['criador'] = hashlib.sha256(tx['recipient'].encode()).hexdigest()[:16]
                    elif tx_type == 'CREATE_SALE_CONTRACT':
                        entry['details']['vendedor'] = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                        entry['details']['preco'] = payload.get('price')
                        entry['details']['condicoes'] = payload.get('conditions')
                    elif tx_type == 'EXECUTE_SALE_CONTRACT':
                        contract = self.get_contracts().get(payload.get('contract_id'))
                        if contract:
                            entry['details']['vendedor'] = hashlib.sha256(contract['seller'].encode()).hexdigest()[:16]
                            entry['details']['comprador'] = hashlib.sha256(tx['sender'].encode()).hexdigest()[:16]
                            entry['details']['preco'] = contract['price']
                    
                    history.append(entry)
        return history
    
    def get_balance(self, address):
        return self.state['balances'].get(address, 0)
    
    def get_owned_tokens(self, address):
        return [token for token, owner in self.state['tokens'].items() if owner == address]

    def get_contracts(self):
        return self.state['contracts']