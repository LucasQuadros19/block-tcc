from ecdsa import SigningKey
import base64
import requests
import json

# Carrega a chave privada da urna
sk = SigningKey.from_pem(open("urna001_priv.pem", "rb").read())

# Dados do voto (eleitor, candidato e urna_id)
id_eleitor = "123456789"
candidato = "Candidato A"
urna_id = "URNA001"

# Mensagem a ser assinada
mensagem = f"{id_eleitor}:{candidato}:{urna_id}"

# Gera a assinatura digital (base64 para enviar em JSON)
assinatura = base64.b64encode(sk.sign(mensagem.encode())).decode()

# Monta o corpo da requisição
payload = {
    "id_eleitor": id_eleitor,
    "candidato": candidato,
    "urna_id": urna_id,
    "assinatura": assinatura
}

# Envia para a API Flask
resposta = requests.post("http://localhost:5000/votar", json=payload)

# Mostra o resultado
print(resposta.status_code)
print(resposta.json())
