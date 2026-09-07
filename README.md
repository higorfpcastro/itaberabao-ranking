# Ranking Itaberabão — automático e gratuito

Este projeto transforma o programa `Torneio_Diario_Itaberabao_v11.py` em uma aplicação que pode rodar automaticamente no GitHub:

**Lichess → GitHub Actions → Python → JSON → GitHub Pages**

A versão não depende de `schedule`, `token.json`, `client_secret.json`, Google Drive ou Spyder.

## O que o sistema faz

1. Consulta os torneios da equipe `itaberabao` na API do Lichess.
2. Seleciona os torneios de interesse.
3. Baixa os resultados de cada torneio.
4. Calcula a classificação geral.
5. Agrupa jogadores com nomes equivalentes.
6. Aplica as correções de pontuação que existiam no programa original.
7. Calcula vencedores e categorias por rating.
8. Gera arquivos JSON em `data/`.
9. Publica automaticamente o site em GitHub Pages.
10. Executa automaticamente uma vez por dia e também pode ser executado manualmente.

## Estrutura

```text
itaberabao-ranking/
├── .github/
│   └── workflows/
│       ├── atualizar.yml
│       └── pages.yml
├── python/
│   └── atualizar.py
├── data/
│   ├── jogadores.json
│   ├── vencedores.json
│   ├── categorias.json
│   ├── torneios.json
│   └── status.json
├── site/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt
├── .gitignore
└── README.md
```

## Passo 1 — criar o repositório

No GitHub, crie um repositório público, por exemplo:

`itaberabao-ranking`

O GitHub Pages está disponível em repositórios públicos no plano GitHub Free, e GitHub Actions é gratuito para repositórios públicos com runners padrão.

## Passo 2 — enviar os arquivos

Envie todo o conteúdo deste projeto para o repositório, mantendo as pastas.

## Passo 3 — ativar o GitHub Pages

No repositório:

**Settings → Pages → Build and deployment → Source → GitHub Actions**

O workflow `pages.yml` fará a publicação.

## Passo 4 — executar a primeira atualização

Abra:

**Actions → Atualizar ranking Itaberabão → Run workflow**

Depois de concluída a execução, abra:

**Actions → Publicar GitHub Pages**

O site será disponibilizado no endereço:

`https://SEU_USUARIO.github.io/itaberabao-ranking/`

## Passo 5 — automatização

O arquivo `atualizar.yml` executa o processamento diariamente às 22:45 no horário de Brasília.

Também existe o acionamento manual (`workflow_dispatch`).

O GitHub usa cron e permite especificar o fuso horário em workflows agendados.

## Importante sobre o primeiro carregamento

O repositório começa com arquivos JSON vazios. Isso é proposital: a primeira execução do GitHub Actions consulta o Lichess e preenche os dados.

## Configurações

As principais configurações estão no início de:

`python/atualizar.py`

Atualmente:

- equipe: `itaberabao`
- data inicial: 18/08/2025
- elimina sábado e domingo
- elimina o torneio `WOE0IJur`
- procura `ITABERAB` ou `Embaixador`
- exige `winner == true`
- mantém a correção `Grillote → Grillito`

As correções de pontuação do programa original também foram preservadas.

## Correções de pontuação preservadas

- `batolsai`, `Hunter04`, `Herzog_Treinamentos`: +2
- `princeofchess`: +3
- `motacta30`, `CCapivara`, `Jesus33`, `macgyversp`, `lafitt`, `danger-perigo`: +4
- `j_erry`: +6
- `AnyPeople`: +8
- `XADREZCSC`: −153

## Google Sheets

A primeira versão do site não precisa de Google Sheets.

Isso elimina:

- `client_secret.json`
- `token.json`
- login OAuth
- dependência de uma máquina ligada

Depois que o site estiver funcionando, podemos adicionar uma segunda etapa para continuar alimentando suas planilhas do Google, se você quiser.

## Observação sobre a lógica

A lógica estatística principal foi mantida baseada no programa original. A diferença é que os dados intermediários agora são mantidos em memória e os resultados finais são publicados como JSON, em vez de depender de vários arquivos Excel intermediários.

## Solução final

Depois de configurado, o fluxo fica:

```text
        Lichess
           │
           ▼
   GitHub Actions
           │
           ▼
      atualizar.py
           │
      ┌────┴────┐
      ▼         ▼
 jogadores   torneios
 vencedores  categorias
      │         │
      └────┬────┘
           ▼
        JSON
           │
           ▼
     GitHub Pages
           │
           ▼
       Site público
```
