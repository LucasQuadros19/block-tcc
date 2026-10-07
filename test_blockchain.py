# Testes das regras da blockchain: hipóteses H1 (imutabilidade) e H2 (contrato atômico)
# do artigo, e o modelo de permissões. Rode com: python -m unittest -v
import copy
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from blockchain import TAX_RATE, Blockchain
from wallet import Wallet

PORT = 9999
NAMES = ("gov", "receita", "cartorio_ctba", "cartorio_sp", "ana", "bruno", "minerador")


def setUpModule():
    global CWD, WALLETS, _wallet_dir
    CWD = os.getcwd()
    _wallet_dir = tempfile.TemporaryDirectory()
    os.chdir(_wallet_dir.name)  # Wallet e Blockchain gravam em data/ relativo ao diretório atual
    WALLETS = {}
    for name in NAMES:
        WALLETS[name] = Wallet()
        WALLETS[name].create_and_save("123", name)
    os.chdir(CWD)


def tearDownModule():
    _wallet_dir.cleanup()


def pk(name):
    return WALLETS[name].public_key.strip()


class RedeTestCase(unittest.TestCase):
    """Governo credencia cartórios em Curitiba e São Paulo; o de Curitiba registra a casa da Ana;
    o Bruno recebe 100 moedas; a Ana pede a venda da casa por 80."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        os.chdir(tmp.name)
        self.addCleanup(tmp.cleanup)
        self.addCleanup(os.chdir, CWD)

        self.bc = Blockchain(PORT, pk("gov"), pk("receita"))
        self.send("gov", pk("cartorio_ctba"), {'type': 'REGISTER_NOTARY', 'payload': {'locality': 'Curitiba'}})
        self.send("gov", pk("cartorio_sp"), {'type': 'REGISTER_NOTARY', 'payload': {'locality': 'São Paulo'}})
        self.send("cartorio_ctba", pk("ana"), {'type': 'MINT_TOKEN', 'payload': {
            'token_id': 'CASA-1', 'asset_type': 'Casa', 'area': '100 m²',
            'locality': 'Curitiba', 'details_hash': 'ab' * 32}})
        self.bc.add_transaction("0", pk("bruno"), "reward", {'type': 'FAUCET'})
        self.mine()
        self.send("ana", "0", {'type': 'REQUEST_SALE_APPROVAL', 'payload': {
            'request_id': 'r1', 'token_id': 'CASA-1', 'price': 80}})

    def mine(self):
        # Minerador neutro: as recompensas de bloco não entram nos saldos verificados.
        self.bc.mine_block(pk("minerador"))

    def send(self, sender, recipient, data):
        tx = {'sender': pk(sender), 'recipient': recipient.strip(), 'data': data}
        signature = Wallet.sign_transaction(WALLETS[sender].private_key, tx)
        ok = self.bc.add_transaction(tx['sender'], tx['recipient'], signature, data)
        if ok:
            self.mine()
        return ok

    def approve(self, valid_until, notary="cartorio_ctba"):
        return self.send(notary, "0", {'type': 'APPROVE_SALE', 'payload': {
            'request_id': 'r1', 'contract_id': 'c1', 'valid_until': valid_until}})

    def buy(self):
        return self.send("bruno", pk("ana"), {'type': 'EXECUTE_SALE_CONTRACT', 'payload': {'contract_id': 'c1'}})

    def owner(self, bc=None):
        owner_pk = (bc or self.bc).state['tokens']['CASA-1']
        return next(name for name in NAMES if pk(name) == owner_pk)


class TestContratoAtomico(RedeTestCase):
    """H2: transferência do ativo, pagamento e ITBI em uma única transação."""

    def test_venda_transfere_ativo_paga_vendedor_e_recolhe_itbi(self):
        self.assertTrue(self.approve(time.time() + 3600))
        self.assertTrue(self.buy())
        tax = int(80 * TAX_RATE)
        self.assertEqual(self.owner(), "bruno")
        self.assertEqual(self.bc.get_balance(pk("bruno")), 100 - 80 - tax)
        self.assertEqual(self.bc.get_balance(pk("ana")), 80)
        self.assertEqual(self.bc.get_balance(pk("receita")), tax)
        self.assertEqual(len(self.bc.get_tax_receipts(pk("bruno"))), 1)

    def test_venda_continua_valida_depois_que_o_contrato_vence(self):
        # Regressão: a validade era comparada com o relógio no momento de reprocessar a cadeia,
        # então reiniciar o nó depois do prazo desfazia a venda.
        self.approve(time.time() + 3600)
        self.buy()
        with mock.patch("blockchain.time.time", return_value=time.time() + 30 * 86400):
            reiniciado = Blockchain(PORT, pk("gov"), pk("receita"))  # recarrega do disco
        self.assertEqual(self.owner(reiniciado), "bruno")

    def test_contrato_vencido_nao_executa(self):
        self.approve(time.time() - 1)
        self.buy()
        self.assertEqual(self.owner(), "ana")
        self.assertEqual(self.bc.get_balance(pk("bruno")), 100)


class TestImutabilidade(RedeTestCase):
    """H1: o histórico não pode ser alterado sem que a rede perceba."""

    def test_alterar_bloco_antigo_invalida_a_cadeia(self):
        # Desvia o FAUCET (transação de sistema, sem assinatura) para a Ana e re-encadeia os
        # blocos seguintes sem refazer o PoW. Antes da correção, essa cadeia era aceita.
        chain = copy.deepcopy(self.bc.chain)
        i, faucet = next((i, tx) for i, block in enumerate(chain) for tx in block['transactions']
                         if tx['transaction']['data'].get('type') == 'FAUCET')
        faucet['transaction']['recipient'] = pk("ana")
        for prev, block in zip(chain[i:], chain[i + 1:]):
            block['previous_hash'] = Blockchain.hash(prev)

        self.assertTrue(self.bc.is_chain_valid(self.bc.chain))
        self.assertFalse(self.bc.is_chain_valid(chain))

        # O mesmo vale para o arquivo em disco: ao reiniciar, o nó descarta a cadeia adulterada.
        with open(self.bc.chain_file, "w") as f:
            json.dump(chain, f)
        self.assertEqual(len(Blockchain(PORT, pk("gov"), pk("receita")).chain), 1)

    def test_bloco_com_transacao_forjada_e_rejeitado(self):
        # Um nó malicioso tenta credenciar o Bruno como cartório "em nome do Governo".
        forged = {'transaction': {'sender': pk("gov"), 'recipient': pk("bruno"),
                                  'data': {'type': 'REGISTER_NOTARY', 'payload': {'locality': 'Curitiba'}}},
                  'signature': '00' * 64}
        self.assertFalse(self.bc.add_block(self.mined_block([forged])))
        self.assertNotIn(pk("bruno"), self.bc.state['authorized_notaries'])

        # A mesma transação, assinada de verdade pelo Governo, é aceita.
        forged['signature'] = Wallet.sign_transaction(WALLETS["gov"].private_key, forged['transaction'])
        self.assertTrue(self.bc.add_block(self.mined_block([forged])))
        self.assertIn(pk("bruno"), self.bc.state['authorized_notaries'])

    def mined_block(self, transactions):
        last = self.bc.last_block
        block = {'index': last['index'] + 1, 'timestamp': time.time(), 'transactions': transactions,
                 'previous_hash': Blockchain.hash(last), 'proof': 0}
        block['proof'] = Blockchain.proof_of_work(block)
        return block


class TestPermissoes(RedeTestCase):
    """Modelo de permissões: Governo credencia, cartório registra e valida na sua localidade."""

    def test_usuario_comum_nao_registra_ativos(self):
        self.assertFalse(self.send("ana", pk("ana"), {'type': 'MINT_TOKEN', 'payload': {
            'token_id': 'CASA-2', 'asset_type': 'Casa', 'area': '1 m²',
            'locality': 'Curitiba', 'details_hash': 'cd' * 32}}))
        self.assertNotIn('CASA-2', self.bc.state['tokens'])

    def test_cartorio_so_valida_vendas_da_sua_localidade(self):
        self.assertFalse(self.approve(time.time() + 3600, notary="cartorio_sp"))
        self.assertEqual(self.bc.get_my_token_status('CASA-1'), "Pendente de Aprovação")

    def test_transferencia_negativa_e_ignorada(self):
        # Sem essa regra, enviar -50 moedas "puxava" saldo do destinatário.
        self.send("ana", pk("bruno"), {'type': 'TRANSFER_CURRENCY', 'payload': {'amount': -50}})
        self.assertEqual(self.bc.get_balance(pk("bruno")), 100)
        self.assertEqual(self.bc.get_balance(pk("ana")), 0)


if __name__ == "__main__":
    unittest.main()
