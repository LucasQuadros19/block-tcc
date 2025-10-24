# config.py
# Este arquivo foi gerado automaticamente por setup.py

# A Chave Pública do "Governo". Esta é a única entidade que pode autorizar novos cartórios.
GOVERNMENT_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEAuJtjVTSiOpFQ5Kw6kJpfrCQzIxV
tlt4UwRpiSknLbtsduTCM/7d9AQdrCrd0RXX1w7LgezeGCXBaNiRj9iO3g==
-----END PUBLIC KEY-----"""

# A Chave Pública do "Órgão Governamental" que recebe os impostos.
TAX_AUTHORITY_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtPKy5r1mlZjSZTaOCqFcG8/37VDN
kI9T18HHrVfewszFv6dl+c+h0CA4eC6AZRsmUlzHa/68uQdEMDZ++xgygA==
-----END PUBLIC KEY-----"""

# A chave do cartório inicial foi removida. O governo deve credenciar o primeiro cartório dinamicamente.
INITIAL_NOTARY_PUBLIC_KEY = None
