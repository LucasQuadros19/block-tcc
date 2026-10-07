# init.py
# Recria a rede local do zero (apaga data/ e regenera config.py):
#   1. carteiras do Governo (Ente Regulador) e da Receita, e o config.py com as chaves públicas;
#   2. dados de demonstração: um cartório em Curitiba, usuários e ativos em vários estágios.
#
#   python init.py          -> rede com dados de demonstração
#   python init.py --vazio  -> só as autoridades (o Governo credencia o 1º cartório pela interface)
#
# Todas as contas usam a senha "123".
import hashlib
import json
import shutil
import sys
import time
import uuid

from wallet import Wallet

PASSWORD = "123"
PORTS = range(5001, 5006)  # os nós de NETWORK_NODES (main.py)


def create_authorities():
    keys = {}
    for name in ("government", "tax_authority"):
        wallet = Wallet()
        if not wallet.create_and_save(PASSWORD, name=name):
            sys.exit(f"Falha ao criar a carteira '{name}'.")
        keys[name] = wallet.public_key
    with open("config.py", "w") as f:
        f.write(f'''# config.py (gerado por init.py)

# Chave pública do Governo (Ente Regulador): única entidade que credencia cartórios.
GOVERNMENT_PUBLIC_KEY = """{keys["government"]}"""

# Chave pública da Receita: recebe o imposto (ITBI) de cada venda.
TAX_AUTHORITY_PUBLIC_KEY = """{keys["tax_authority"]}"""
''')
    return keys


def seed_demo(keys):
    from blockchain import Blockchain
    from main import OffChainDBManager, SimpleUserManager  # só depois do config.py existir

    users = SimpleUserManager()
    for name in ("cartorio_curitiba", "ana", "bruno"):
        users.register(name, PASSWORD)

    def load(name):
        wallet = Wallet()
        wallet.load(PASSWORD, name)
        return wallet
    gov, cartorio, ana, bruno = (load(n) for n in ("government", "cartorio_curitiba", "ana", "bruno"))

    bc = Blockchain(5001, keys["government"], keys["tax_authority"])
    offchain_db = OffChainDBManager(5001)  # o cartório de Curitiba opera no nó 5001

    def send(sender, recipient, data):
        # Mesmo fluxo da interface: assina, entra na pool e o próprio remetente minera.
        tx = {'sender': sender.public_key.strip(), 'recipient': recipient.strip(), 'data': data}
        signature = Wallet.sign_transaction(sender.private_key, tx)
        assert bc.add_transaction(tx['sender'], tx['recipient'], signature, data), data['type']
        bc.mine_block(sender.public_key)

    def mint(owner, asset_type, area, owner_name, owner_cpf, address):
        offchain_data = {
            "owner_name": owner_name,
            "owner_cpf": owner_cpf,
            "full_address": address,
            "documents_mock": "http://exemplo.com/doc/matricula.pdf",
            "registered_by_notary_pk": cartorio.public_key.strip(),
            "registered_at": time.time()
        }
        details_hash = hashlib.sha256(json.dumps(offchain_data, sort_keys=True).encode()).hexdigest()
        offchain_db.save_asset_details(details_hash, offchain_data)
        token_id = f"{asset_type.replace(' ', '-').upper()}-[{str(uuid.uuid4()).upper()[:8]}]"
        send(cartorio, owner.public_key, {'type': 'MINT_TOKEN', 'payload': {
            'token_id': token_id, 'asset_type': asset_type, 'area': area,
            'locality': 'Curitiba', 'details_hash': details_hash}})
        return token_id

    def request_sale(owner, token_id, price):
        request_id = str(uuid.uuid4())
        send(owner, "0", {'type': 'REQUEST_SALE_APPROVAL', 'payload': {
            'request_id': request_id, 'token_id': token_id, 'price': price}})
        return request_id

    def approve(request_id, hours):
        contract_id = str(uuid.uuid4())
        send(cartorio, "0", {'type': 'APPROVE_SALE', 'payload': {
            'request_id': request_id, 'contract_id': contract_id, 'valid_until': time.time() + hours * 3600}})
        return contract_id

    send(gov, cartorio.public_key, {'type': 'REGISTER_NOTARY', 'payload': {'locality': 'Curitiba'}})
    bc.add_transaction("0", bruno.public_key, "reward", {'type': 'FAUCET'})
    bc.mine_block(bruno.public_key)

    casa = mint(ana, "Casa", "180 m²", "Ana Souza", "111.111.111-11", "Rua das Flores, 10 - Curitiba/PR")
    apartamento = mint(ana, "Apartamento", "72 m²", "Ana Souza", "111.111.111-11",
                       "Av. Sete de Setembro, 500, ap. 41 - Curitiba/PR")
    terreno = mint(bruno, "Terreno Urbano", "450 m²", "Bruno Lima", "222.222.222-22",
                   "Rua XV de Novembro, 900 - Curitiba/PR")

    # Venda concluída: a casa passa para o Bruno e o ITBI vai para a Receita na mesma transação.
    contract = approve(request_sale(ana, casa, 150), hours=24)
    send(bruno, ana.public_key, {'type': 'EXECUTE_SALE_CONTRACT', 'payload': {'contract_id': contract}})
    # Apartamento aprovado e à venda no Marketplace por 7 dias.
    approve(request_sale(ana, apartamento, 90), hours=24 * 7)
    # Terreno aguardando a validação do cartório.
    request_sale(bruno, terreno, 200)

    for port in PORTS[1:]:  # todos os nós começam com a mesma cadeia
        shutil.copy(bc.chain_file, bc.chain_file.replace("5001", str(port)))
    print(f"\nDados de demonstração criados: {len(bc.chain)} blocos.")


if __name__ == "__main__":
    demo = "--vazio" not in sys.argv
    shutil.rmtree("data", ignore_errors=True)
    keys = create_authorities()
    if demo:
        seed_demo(keys)
    accounts = "government, tax_authority" + (", cartorio_curitiba, ana, bruno" if demo else "")
    print(f"\nPronto. Contas (senha {PASSWORD}): {accounts}")
    print("Abra um nó por terminal: python main.py 5001  (e 5002, 5003... para simular a rede)")
