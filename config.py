# config.py
# Este arquivo foi gerado automaticamente por setup.py

# A Chave Pública do "Governo". Esta é a única entidade que pode autorizar novos cartórios.
GOVERNMENT_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEC3ybBw98u4jwWaYIrY8g0/ronFHL
4VhRHt+SaVnJfMDC636QD16Lajh2ZKFSe4H1MuNHWq9PzOkzbKKAKiEsIg==
-----END PUBLIC KEY-----"""

# A Chave Pública do "Órgão Governamental" que recebe os impostos.
TAX_AUTHORITY_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfojxYyiLX164wTKhYWoughS4KyUX
u5RtF8ZkHKT6zW5vGqryOIR5y5dJQjA79a2fO7Fpo8fZow3ZhlSvmML1IA==
-----END PUBLIC KEY-----"""

# A chave do cartório inicial foi removida. O governo deve credenciar o primeiro cartório dinamicamente.
INITIAL_NOTARY_PUBLIC_KEY = None
