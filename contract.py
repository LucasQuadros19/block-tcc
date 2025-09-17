# contract.py

class Contract:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.contracts = []

    def create_contract(self, contract_text):
        contract_id = len(self.contracts) + 1
        contract = {
            'contract_id': contract_id,
            'contract_text': contract_text
        }
        self.contracts.append(contract)
        return contract

    def get_contracts(self):
        return self.contracts
