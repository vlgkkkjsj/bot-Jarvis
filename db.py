import sqlite3

conn = sqlite3.connect('ranking.db')
cursor = conn.cursor()

def init_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            guild_id INTEGER,
            xp INTEGER DEFAULT 0,
            vitorias INTEGER DEFAULT 0,
            derrotas INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, guild_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loja(
            guild_id INTEGER,
            tipo TEXT,
            product_name TEXT,
            description TEXT, 
            price INTEGER,
            PRIMARY KEY (guild_id, product_name)
        )
    ''')
    conn.commit()


# XP INCREMENT
def add_xp(user_id: int, guild_id: int, amount: int):
    ensure_user_exists(user_id, guild_id)
    
    try:
        cursor.execute('''
            UPDATE users
            SET xp = xp + ?
            WHERE user_id = ? AND guild_id = ?    
        ''', (amount, user_id, guild_id))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao adicionar XP ao usuário {user_id}: {e}")
        return False

# EXISTENCE CHECKERS

def user_exists(user_id, guild_id):
    cursor.execute('SELECT 1 FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    return cursor.fetchone() is not None

def guild_exists(guild_id):
    cursor.execute('SELECT 1 FROM loja WHERE guild_id = ? LIMIT 1', (guild_id,))
    return cursor.fetchone() is not None

def ensure_user_exists(user_id, guild_id):
    if not user_exists(user_id, guild_id):
        set_user_data(user_id, guild_id, 0, 0, 0)

def set_user_data(user_id, guild_id, xp, vitorias, derrotas):
    cursor.execute('''
        INSERT INTO users (user_id, guild_id, xp, vitorias, derrotas)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, guild_id) DO UPDATE SET
            xp = excluded.xp,
            vitorias = excluded.vitorias,
            derrotas = excluded.derrotas;
    ''', (user_id, guild_id, xp, vitorias, derrotas))
    conn.commit()

# UPDATE FUNCTIONS DATABASE

def clear_user_data(user_id, guild_id):
    cursor.execute('''
        UPDATE users SET xp = 0, vitorias = 0, derrotas = 0
        WHERE user_id = ? AND guild_id = ?
    ''', (user_id, guild_id))
    conn.commit()

def update_user_data(user_id, guild_id, xp, vitorias, derrotas):
    try:
        with conn:
            cursor.execute('''
                UPDATE users SET
                    xp = ?,
                    vitorias = ?,
                    derrotas = ?
                WHERE user_id = ? AND guild_id = ?
            ''', (xp, vitorias, derrotas, user_id, guild_id))
    except sqlite3.Error as e:
        print(f"[ERRO] Failed to update user data {user_id}: {e}")

def update_xp(user_id, guild_id, xp):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] Usuário {user_id} não encontrado")
        return None
    try:
        cursor.execute('UPDATE users SET xp = ? WHERE user_id = ? AND guild_id = ?', (xp, user_id, guild_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao atualizar XP do usuário {user_id}: {e}")
        return None

def update_vitorias(user_id, guild_id, vitorias):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] Usuário {user_id} não encontrado")
        return None
    try:
        cursor.execute('UPDATE users SET vitorias = ? WHERE user_id = ? AND guild_id = ?', (vitorias, user_id, guild_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao atualizar vitórias do usuário {user_id}: {e}")
        return None

def update_derrotas(user_id, guild_id, derrotas):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] Usuário {user_id} não encontrado")
        return None
    try:
        cursor.execute('UPDATE users SET derrotas = ? WHERE user_id = ? AND guild_id = ?', (derrotas, user_id, guild_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[ERRO] Falha ao atualizar derrotas do usuário {user_id}: {e}")
        return None

# GET FUNCTIONS    
def get_user_data(user_id, guild_id):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] usuario {user_id} não encontrado")
        return None
    try:
        cursor.execute('SELECT xp, vitorias, derrotas FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"[ERRO] Falha na requisicao de dados {user_id}: {e}")
        return None

def get_top_users(guild_id, limit=10):
    cursor.execute(
        "SELECT user_id, xp, vitorias, derrotas FROM users WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
        (guild_id, limit)
    )
    return cursor.fetchall()

# DELETE FUNCTIONS

def delete_user(user_id):
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.commit()

def reset_user_xp(user_id, guild_id):
    if not user_exists(user_id, guild_id):
        print(f"[AVISO] usuario {user_id} não encontrado")
        return None
    try:
        cursor.execute('UPDATE users SET xp = 0 WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[ERRO] Falha na execucao do UPDATE de XP {user_id}: {e}")

def reset_user_lose(user_id, guild_id):
    cursor.execute('UPDATE users SET derrotas = 0 WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    conn.commit()

def reset_user_win(user_id, guild_id):
    cursor.execute('UPDATE users SET vitorias = 0 WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    conn.commit()

# SHOP FUNCTIONS

def guild_items_exists(guild_id, product_name):
    cursor.execute('SELECT 1 FROM loja WHERE guild_id = ? AND product_name = ?', (guild_id, product_name))
    return cursor.fetchone() is not None

def get_items_shop(guild_id):
    try:
        cursor.execute('SELECT * FROM loja WHERE guild_id=? ORDER BY price DESC', (guild_id,))
        items = cursor.fetchall()
        if not items:
            print(f'[WARNING] Servidor sem items encontrados {guild_id}')
            return None
        return items
    except sqlite3.Error as e:
        print(f'[ERROR] erro ao selecionar items da loja {e}')
        return None

def set_item_shop(guild_id, tipo, product_name, description, price):
    try:
        cursor.execute('''
            INSERT INTO loja (guild_id, tipo, product_name, description, price)
            VALUES (?, ?, ?, ?, ?)
        ''', (guild_id, tipo, product_name, description, price))
        conn.commit()
        print("Item criado com sucesso.")
    except sqlite3.IntegrityError:
        print("Item já existe! Não foi criado.")

def ensure_guild_shop_exists(guild_id):
    try:
        cursor.execute('SELECT 1 FROM loja WHERE guild_id = ? LIMIT 1', (guild_id,))
        result = cursor.fetchone()
        if result is None:
            cursor.execute('''
                INSERT INTO loja (guild_id, product_name, description, price)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, None, None, None))
            conn.commit()
            print(f'[INFO] Loja do servidor inicializada {guild_id}')
        else:
            print(f'[INFO] Loja do servidor já existe para o servidor {guild_id}')
    except sqlite3.Error as e:
        print(f'[ERRO] erro detectado ao verificar a loja do servidor {guild_id} : {e}')
