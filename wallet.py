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

class Wallet:
    def __init__(self, username=None, password=None):
        self.wallets_dir = "data/wallets"
        os.makedirs(self.wallets_dir, exist_ok=True)

        if username and password:
            try:
                self.private_key, self.public_key = self.load_keys(username, password)
            except (ValueError, KeyError):
                # Isso vai acontecer se a senha estiver errada
                raise ValueError("Senha incorreta ou arquivo da carteira corrompido.")
        else:
            self.private_key = None
            self.public_key = None

    def create_keys(self):
        key = ECC.generate(curve='P-256')
        self.private_key = key.export_key(format='PEM')
        self.public_key = key.public_key().export_key(format='PEM')
        return self.private_key, self.public_key

    def save_keys(self, username, password):
        if self.private_key and self.public_key:
            # Criptografa a chave privada usando a senha do usuário
            salt = get_random_bytes(16)
            key = PBKDF2(password, salt, dkLen=32) # Deriva uma chave da senha
            cipher = AES.new(key, AES.MODE_GCM)
            encrypted_private_key, tag = cipher.encrypt_and_digest(self.private_key.encode('utf-8'))

            # Salva tudo necessário para descriptografar depois
            with open(os.path.join(self.wallets_dir, f'{username}_wallet.json'), 'w') as f:
                json.dump({
                    'salt': binascii.hexlify(salt).decode(),
                    'nonce': binascii.hexlify(cipher.nonce).decode(),
                    'tag': binascii.hexlify(tag).decode(),
                    'ciphertext': binascii.hexlify(encrypted_private_key).decode()
                }, f)

            # A chave pública não precisa ser secreta
            with open(os.path.join(self.wallets_dir, f'{username}_public.pem'), 'w') as f:
                f.write(self.public_key)
            
            print(f"Carteira para {username} criada e criptografada com sucesso.")

    def load_keys(self, username, password):
        try:
            # Carrega a chave pública
            with open(os.path.join(self.wallets_dir, f'{username}_public.pem'), 'r') as f:
                public_key = f.read()
            self.public_key = public_key

            # Carrega e descriptografa a chave privada
            with open(os.path.join(self.wallets_dir, f'{username}_wallet.json'), 'r') as f:
                data = json.load(f)
            
            salt = binascii.unhexlify(data['salt'])
            nonce = binascii.unhexlify(data['nonce'])
            tag = binascii.unhexlify(data['tag'])
            ciphertext = binascii.unhexlify(data['ciphertext'])
            
            key = PBKDF2(password, salt, dkLen=32)
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            private_key = cipher.decrypt_and_verify(ciphertext, tag).decode('utf-8')
            
            self.private_key = private_key
            return private_key, public_key
        
        except FileNotFoundError:
            print(f"Carteira para {username} não encontrada. Criando uma nova.")
            self.create_keys()
            self.save_keys(username, password)
            return self.private_key, self.public_key

    @staticmethod
    def sign_transaction(private_key_pem, transaction):
        key = ECC.import_key(private_key_pem)
        signer = DSS.new(key, 'fips-186-3')
        tx_string = json.dumps(transaction, sort_keys=True).encode('utf-8')
        h = SHA256.new(tx_string)
        signature = signer.sign(h)
        return binascii.hexlify(signature).decode('ascii')

    @staticmethod
    def verify_transaction(public_key_pem, transaction, signature):
        try:
            key = ECC.import_key(public_key_pem)
            verifier = DSS.new(key, 'fips-186-3')
            tx_string = json.dumps(transaction, sort_keys=True).encode('utf-8')
            h = SHA256.new(tx_string)
            verifier.verify(h, binascii.unhexlify(signature))
            return True
        except (ValueError, TypeError):
            return False