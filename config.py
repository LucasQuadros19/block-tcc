# config.py
# Este arquivo foi gerado automaticamente por setup.py

# A Chave Pública do "Governo". Esta é a única entidade que pode autorizar novos cartórios.
GOVERNMENT_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6K/HN7q4GC5PRiUFHrP9qGvXuX6g
q7Pf6vDL22GhsV/OJtPz3lCc2SBpE/jGtauPOkRJkN9RJ8G6RJ8rhmoQyg==
-----END PUBLIC KEY-----"""

# A Chave Pública do "Órgão Governamental" que recebe os impostos.
TAX_AUTHORITY_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtmh+t3YiaOI+pIhKB2Opaxp0aZTo
KrdHOcEqp99QQRBJrSWM8DgIoHUMNmQ1X85O58q85f/KBqhvIKS+8Wzmsw==
-----END PUBLIC KEY-----"""

# A chave do cartório inicial foi removida. O governo deve credenciar o primeiro cartório dinamicamente.
INITIAL_NOTARY_PUBLIC_KEY = None
