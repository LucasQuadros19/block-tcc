# Blockchain e Contratos Inteligentes nos Cartórios Brasileiros

Prova de Conceito (PoC) do TCC **"Blockchain e Contratos Inteligentes nos Cartórios Brasileiros: Redução de Burocracia e Ganhos de Eficiência"**, do curso de Engenharia de Software do Centro Universitário Descomplica Uniamérica (2025).

**[Leia o artigo completo (PDF)](<Blockchain e Contratos Inteligentes nos Cartórios Brasileiros_ Redução de Burocracia e Ganhos de Eficiência..pdf>)**

É uma rede blockchain simulada em Python que segue a tese "Evolução, não Extinção": o cartório não é substituído pela tecnologia, mas passa a ser um validador da rede.

- O **Ente Regulador (Governo)** credencia cartórios por localidade.
- O **Cartório** registra imóveis como tokens (NFT) e aprova ou recusa os pedidos de venda da sua localidade.
- O **Usuário** pede a venda dos próprios imóveis e compra os que estão à venda.

## O que a PoC demonstra

| Hipótese | Como aparece no sistema |
|---|---|
| **H1:** segurança e imutabilidade sem expor dados pessoais | Arquitetura híbrida: nome, CPF e endereço ficam no banco local do cartório (off-chain), e só o hash desses dados vai para a blockchain. Toda transação é assinada (ECDSA P-256), e o Proof-of-Work cobre o conteúdo inteiro de cada bloco. |
| **H2:** eficiência via contrato inteligente | Na transação `EXECUTE_SALE_CONTRACT`, de uma só vez, o comprador paga, o vendedor recebe, o ITBI (5%) vai para a Receita e o token muda de dono. |
| **H3:** transparência com privacidade | O Block Explorer e o Explorador de Ativos mostram o histórico completo de cada imóvel, com os donos identificados só pela chave pública. |

## Como rodar

É preciso ter Python 3.9 ou superior, com Tkinter.

```bash
python -m venv .venv && source .venv/bin/activate   # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python init.py        # cria a rede do zero com dados de demonstração (ou: python init.py --vazio)
python main.py 5001   # abre um nó: a janela e a API na porta 5001
```

Para simular a rede, abra mais nós em outros terminais (`python main.py 5002` e assim por diante, até 5005). Cada nó guarda sua própria cópia da cadeia, e a cada 10 segundos os nós se sincronizam adotando a maior cadeia válida.

> **macOS:** o Python que vem com o sistema (`/usr/bin/python3`) traz um Tk antigo, que não abre nas versões recentes do macOS. Use o Python do [python.org](https://www.python.org/downloads/) ou, se usar Homebrew, rode `brew install python-tk@3.12`.

### Contas da demonstração (senha `123` em todas)

| Conta | Papel | O que experimentar |
|---|---|---|
| `bruno` | Usuário | Comprar o apartamento no Marketplace e ver o recibo do ITBI em "Meu Perfil", ou pedir a venda da casa que ele já comprou |
| `ana` | Usuária | Ver o apartamento à venda em "Meu Perfil" e o histórico da casa que ela vendeu no "Explorador de Ativos" |
| `cartorio_curitiba` | Cartório de Curitiba | Em "Validar Vendas", aprovar ou recusar o terreno do Bruno. Use o **nó 5001**, que tem os dados off-chain |
| `government` | Ente Regulador | Credenciar um novo cartório (a chave pública de cada usuário aparece em "Meu Perfil") |
| `tax_authority` | Receita | Ver o saldo do ITBI arrecadado |

A demonstração já inclui uma venda concluída (a casa da Ana, comprada pelo Bruno), que pode ser vista no "Explorador de Ativos".

## Testes

```bash
python -m unittest -b -v
```

Os testes cobrem o contrato atômico com ITBI (H2), a rejeição de histórico adulterado e de transações forjadas (H1) e o modelo de permissões: só o cartório registra ativos, e cada cartório só valida vendas da sua localidade.

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `blockchain.py` | Cadeia, Proof-of-Work, regras de consenso (estado, contratos, ITBI) e sincronização entre nós |
| `wallet.py` | Carteiras: chaves ECC P-256, assinaturas e chave privada cifrada com AES-GCM |
| `main.py` | Aplicação: telas, contas de usuário, banco off-chain e API Flask entre os nós |
| `gui.py` | Layout da interface (CustomTkinter) |
| `init.py` | Gera as carteiras das autoridades, o `config.py` e os dados de demonstração |
| `test_blockchain.py` | Testes automatizados |
| `data/` | Criado ao rodar o projeto: carteiras, a cadeia de cada nó e os bancos off-chain |

## Limites e diferenças em relação ao artigo

Este projeto é uma prova de conceito, não um sistema de produção:
- a rede P2P usa uma lista fixa de nós;
- tudo é armazenado em arquivos JSON;
- o Proof-of-Work tem dificuldade baixa, e cada usuário minera o próprio bloco;
- as transações usam moedas de teste.

A seção 5.2 do artigo detalha esses limites.

Depois da entrega do artigo, o código recebeu algumas correções e ganhou testes automatizados:
- o Proof-of-Work passou a cobrir todo o conteúdo do bloco;
- as assinaturas dos blocos recebidos da rede passaram a ser verificadas;
- a validade dos contratos passou a usar o horário do bloco (antes, uma venda podia ser desfeita ao reiniciar o nó).

Os Quadros 1 e 2 do artigo são trechos simplificados do código. A biblioteca Pillow, citada no artigo, não é necessária.

## Autores

Lucas Eduardo Alves de Quadros e Pedro Bulla Lima.
Orientador: Prof. Gildomiro Bairros. Professora de Projeto Final de Curso: Profa. Dra. Isabel Fernandes.
