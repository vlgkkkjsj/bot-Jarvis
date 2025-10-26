# JarvisBot

JarvisBot é um bot multifuncional para Discord, com foco em **XP, moderação, música, loja personalizada e interações sociais**. Ele é projetado para servidores que querem engajar usuários com sistemas de recompensas e comandos úteis.

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
  - **/info** — Abre as informações de um usuario no servidor

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

### 📊 XP
- **/getxp** — Exibe seus dados de XP.
- **/ranking** — Mostra os 10 usuários com mais XP no servidor.

---

## 🛠️ Instalação

```bash
git clone https://github.com/SEU_USUARIO/JarvisBot.git
cd JarvisBot
pip install -r requirements.txt
