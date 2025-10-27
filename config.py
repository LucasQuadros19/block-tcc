# config.py
# Este arquivo foi gerado automaticamente por setup.py

# A Chave Pública do "Governo". Esta é a única entidade que pode autorizar novos cartórios.
GOVERNMENT_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUuEZBhJBndAmZ5tVC2jH/2imSScY
FMbuQKdzdQ26HXrNQIO3c7cpTqcXsWhxCPXflaE3uxsjbD92w/AxrGT0ng==
-----END PUBLIC KEY-----"""

# A Chave Pública do "Órgão Governamental" que recebe os impostos.
TAX_AUTHORITY_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEWBfgagK2IxmCkMMPkjqptrh0gtQX
RLvpdFetPujtkVRTtCD9HedoHh4yec1kraErjcNDqFoHQKuyxgAhbnbU2g==
-----END PUBLIC KEY-----"""

# A chave do cartório inicial foi removida. O governo deve credenciar o primeiro cartório dinamicamente.
INITIAL_NOTARY_PUBLIC_KEY = None
