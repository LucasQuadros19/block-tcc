# setup.py
# Execute este script UMA VEZ para criar as carteiras das autoridades
# e gerar o arquivo de configuração (config.py).

from wallet import Wallet
import os
import sys  # Para sair em caso de erro

print("--- Configuração Inicial da Rede ---")
print("Criando automaticamente as carteiras das autoridades da blockchain.")

# Garante que os diretórios existam
wallet_dir = os.path.join("data", "wallets")
os.makedirs(wallet_dir, exist_ok=True)

# --- Criação da Carteira do Governo ---
print("\n[1/2] Criando a carteira do GOVERNO...")
gov_wallet = Wallet()
gov_password = "123"  # Senha fixa
if gov_wallet.create_and_save(gov_password, name="government"):
    GOVERNMENT_PUBLIC_KEY = gov_wallet.public_key
    print("Carteira do Governo criada com sucesso (senha: 123).")
else:
    print("ERRO: Falha ao criar carteira do Governo.")
    sys.exit(1)

# --- Criação da Carteira da Autoridade Fiscal ---
print("\n[2/2] Criando a carteira da AUTORIDADE FISCAL (IMPOSTOS)...")
tax_wallet = Wallet()
tax_password = "123"  # Senha fixa
if tax_wallet.create_and_save(tax_password, name="tax_authority"):
    TAX_AUTHORITY_PUBLIC_KEY = tax_wallet.public_key
    print("Carteira da Autoridade Fiscal criada com sucesso (senha: 123).")
else:
    print("ERRO: Falha ao criar carteira da Autoridade Fiscal.")
    sys.exit(1)

# --- Geração do arquivo config.py ---
if GOVERNMENT_PUBLIC_KEY is None or TAX_AUTHORITY_PUBLIC_KEY is None:
    print("\nERRO CRÍTICO: Falha ao gerar chaves públicas. Abortando.")
    sys.exit(1)

config_content = f'''# config.py
# Este arquivo foi gerado automaticamente por setup.py

# A Chave Pública do "Governo". Esta é a única entidade que pode autorizar novos cartórios.
GOVERNMENT_PUBLIC_KEY = """{GOVERNMENT_PUBLIC_KEY}"""

# A Chave Pública do "Órgão Governamental" que recebe os impostos.
TAX_AUTHORITY_PUBLIC_KEY = """{TAX_AUTHORITY_PUBLIC_KEY}"""

# A chave do cartório inicial foi removida. O governo deve credenciar o primeiro cartório dinamicamente.
INITIAL_NOTARY_PUBLIC_KEY = None
'''

try:
    with open("config.py", "w") as f:
        f.write(config_content)
    print("\n--- Configuração Concluída! ---")
    print("O arquivo 'config.py' foi gerado com as chaves públicas corretas.")
    print("Os arquivos de carteira criptografados foram salvos em 'data/wallets/'.")
    print("Senha de ambas as carteiras: 123")
except IOError as e:
    print(f"\nERRO ao escrever config.py: {e}")
    sys.exit(1)
