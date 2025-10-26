# wallet.py
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import binascii
import json
import os

WALLET_DIR = os.path.join("data", "wallets")

class Wallet:
    def __init__(self):
        self.private_key = None
        self.public_key = None
        os.makedirs(WALLET_DIR, exist_ok=True)

    def _get_paths(self, name):
        """Retorna os caminhos dos arquivos de chave com base no nome."""
        private_key_file = os.path.join(WALLET_DIR, f"{name}_wallet.json")
        public_key_file = os.path.join(WALLET_DIR, f"{name}_public.pem")
        return private_key_file, public_key_file

    def wallet_exists(self, name):
        """Verifica se um arquivo de carteira com o nome especificado já existe."""
        private_key_file, _ = self._get_paths(name)
        return os.path.exists(private_key_file)

    def create_and_save(self, password, name):
        if not password:
            raise ValueError("Senha não pode estar em branco.")
            
        private_key_file, public_key_file = self._get_paths(name)
        
        # Previne sobrescrever carteiras
        if os.path.exists(private_key_file):
             print(f"AVISO: A carteira '{name}' já existe. Não será sobrescrevida.")
             # Tenta carregar a chave pública existente como fallback
             try:
                 # CORREÇÃO: Remove .strip() para carregar a chave como está no arquivo
                 with open(public_key_file, 'r') as f: self.public_key = f.read()
                 self.private_key = None # Não temos a senha para carregar a privada
                 return True # Indica sucesso parcial (só carregou pública)
             except FileNotFoundError:
                 print(f"ERRO: Arquivo da chave pública '{public_key_file}' não encontrado.")
                 return False

        key = ECC.generate(curve='P-256')
        self.private_key = key.export_key(format='PEM')
        # CORREÇÃO: Remove .strip() para armazenar a chave PEM completa (multi-linha)
        self.public_key = key.public_key().export_key(format='PEM')

        salt = get_random_bytes(16)
        derived_key = PBKDF2(password, salt, dkLen=32)
        cipher = AES.new(derived_key, AES.MODE_GCM)
        encrypted_private_key, tag = cipher.encrypt_and_digest(self.private_key.encode('utf-8'))

        try:
            with open(private_key_file, 'w') as f:
                json.dump({
                    'salt': binascii.hexlify(salt).decode(),
                    'nonce': binascii.hexlify(cipher.nonce).decode(),
                    'tag': binascii.hexlify(tag).decode(),
                    'ciphertext': binascii.hexlify(encrypted_private_key).decode()
                }, f)

            with open(public_key_file, 'w') as f:
                # Salva a chave completa (multi-linha)
                f.write(self.public_key)
            
            print(f"Nova carteira '{name}' criada com sucesso.")
            return True
        except IOError as e:
            print(f"Erro ao salvar arquivos da carteira '{name}': {e}")
            # Tenta limpar arquivos criados parcialmente
            if os.path.exists(private_key_file): os.remove(private_key_file)
            if os.path.exists(public_key_file): os.remove(public_key_file)
            return False


    def load(self, password, name):
        private_key_file, public_key_file = self._get_paths(name)
        
        if not self.wallet_exists(name):
             print(f"Tentativa de carregar carteira '{name}' que não existe.")
             return False
        
        try:
            with open(public_key_file, 'r') as f:
                # CORREÇÃO: Remove .strip() para carregar a chave como está no arquivo
                self.public_key = f.read()

            with open(private_key_file, 'r') as f:
                data = json.load(f)
            
            salt = binascii.unhexlify(data['salt'])
            nonce = binascii.unhexlify(data['nonce'])
            tag = binascii.unhexlify(data['tag'])
            ciphertext = binascii.unhexlify(data['ciphertext'])
            
            derived_key = PBKDF2(password, salt, dkLen=32)
            cipher = AES.new(derived_key, AES.MODE_GCM, nonce=nonce)
            private_key_bytes = cipher.decrypt_and_verify(ciphertext, tag)
            self.private_key = private_key_bytes.decode('utf-8')
            
            # print(f"Carteira '{name}' carregada com sucesso.") # Descomente para depurar
            return True
        except (ValueError, KeyError, FileNotFoundError, binascii.Error) as e: # Adicionado binascii.Error
            print(f"Erro ao carregar carteira '{name}': {e}. Senha incorreta ou arquivo corrompido?")
            self.private_key = None
            self.public_key = None
            return False

    @staticmethod
    def sign_transaction(private_key_pem, transaction):
        try:
            key = ECC.import_key(private_key_pem)
            signer = DSS.new(key, 'fips-186-3')
            tx_string = json.dumps(transaction, sort_keys=True, separators=(',', ':')).encode('utf-8')
            h = SHA256.new(tx_string)
            signature = signer.sign(h)
            return binascii.hexlify(signature).decode('ascii')
        except Exception as e:
            print(f"Erro ao assinar transação: {e}")
            return None


    @staticmethod
    def verify_transaction(public_key_pem, transaction, signature):
        try:
            # CORREÇÃO MANTIDA: A biblioteca de criptografia precisa da chave limpa
            key = ECC.import_key(public_key_pem.strip())
            verifier = DSS.new(key, 'fips-186-3')
            tx_string = json.dumps(transaction, sort_keys=True, separators=(',', ':')).encode('utf-8')
            h = SHA256.new(tx_string)
            verifier.verify(h, binascii.unhexlify(signature))
            return True
        except (ValueError, TypeError, binascii.Error) as e:
            # print(f"Erro na verificação da assinatura: {e}") # Descomente para depurar
            return False

