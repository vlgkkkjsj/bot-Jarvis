# JarvisBot

JarvisBot é um bot multifuncional para Discord, com foco em **XP, moderação, música, loja personalizada, interações sociais e desafios (Challenge)**. Ele é ideal para servidores que querem engajar usuários com sistemas de recompensas, competições e comandos úteis.

---

## ⚡ Funcionalidades Principais

### 🔧 Administração
- **/setxp** — Define XP, vitórias e derrotas de um usuário.
- **/clsdata** — Zera todos os dados do servidor.
- **/updata** — Atualiza todos os dados do servidor.
- **/delxp** — Zera apenas o XP dos usuários.

### 🛡️ Champion
- **/champion** — Escolhe aleatoriamente um champion do LoL, de acordo com a lane.

### 💬 Interação
- **Sistema de XP automático**:
  - 15 minutos em chat de voz = 15 XP
  - 10 minutos em chat de texto = 10 XP
- **/info** — Abre as informações de um usuário no servidor.
- **/givebadge** — Dar uma badge a um usuário (admin apenas).
- **/removebadge** — Remover badges de um usuário (admin apenas).

### 🛒 Loja
- **/loja** — Abre a loja do servidor.
- **/cfg** — Mostra configurações da compra do usuário.
- **/cfgname** — Alterar o nome do cargo VIP.
- **/cfgcolor** — Alterar a cor do cargo VIP.
- **/cfgcall** — Configurar a call VIP.
- **/addtag** — Dar seu cargo VIP a outro usuário.
- **/nvitem** — Adiciona um novo item à loja personalizada.

### ⚖️ Moderação
- **/mute** — Muta um usuário.
- **/ban** — Bane um usuário do servidor.
- **/punishments** — Mostra o histórico de punições de um usuário.

### 🎶 Música
- **/play** — Toca uma música.
- **/resume** — Continua a música pausada.
- **/pause** — Pausa a música.
- **/loop** — Define loop da música.
- **/queue** — Mostra a fila de músicas.
- **/skip** — Pula a música atual.
- **/shuffle** — Embaralha a fila de músicas.

### 😂 Social
- **/meme** — Envia um meme aleatório.
- **/casar** — Pede um usuário em casamento.
- **/divorcio** — Pede divórcio do casamento.

### 🧠 Challenge (Desafios)
**Comandos principais do módulo Challenge:**
| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/challenge_start` | Cria um novo desafio (abre modal para definir nome, tema, tecnologias, período e descrição) | Admin |
| `/entrar` | Entra no desafio ativo atual | Todos |
| `/sair_time` | Sai do time atual do desafio | Todos |
| `/sair_desafio` | Sai completamente do desafio, removendo o usuário de todos os times | Todos |
| `/sortear_times [num_times]` | Sorteia os times do desafio ativo. `num_times` define a quantidade de times | Admin |
| `/ver_times` | Mostra todos os times formados e informações do desafio ativo | Todos |
| `/participants` | Mostra todos os participantes do desafio | Admin |
| `/end_challenge` | Encerra o desafio ativo | Admin |

**Funcionalidades interativas:**
- 🔄 Atualizar Times: atualiza a lista de times em tempo real.  
- 🔄 Atualizar Participantes: atualiza a lista de participantes em tempo real.  
- ⬅️ / ➡️: navegação entre páginas de participantes.

### 📊 XP
- **/getxp** — Exibe seus dados de XP.
- **/ranking** — Mostra os 10 usuários com mais XP no servidor.

---

## 🛠️ Instalação

```bash
git clone https://github.com/vlgkkkjsj/bot-Jarvis
cd JarvisBot
pip install -r requirements.txt
