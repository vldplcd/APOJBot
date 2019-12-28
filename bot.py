import os, flask, io
from flask import Flask
import telebot, logging, random, requests, boto3
from pydub import AudioSegment

logger = telebot.logger
telebot.logger.setLevel(logging.DEBUG)

app = Flask(__name__)
BASE_DIR = os.path.dirname(app.instance_path)

S3_BUCKET = os.environ.get('S3_BUCKET')
s3 = boto3.client('s3')

secret = "971010"

# apihelper.proxy = {'https':'http://voland.jos@gmail.com:josyka1994vpn@fi-esp.pvdata.host:8080'}
API_TOKEN = "1056456602:AAGdeyzA92S98aO3PrJLF0DS-xlG4nkwWAU"
bot = telebot.TeleBot(API_TOKEN)
request_kwargs = {'proxy_url': 'socks5h://fi-esp.pvdata.host:1080/',
                  'urllib3_proxy_kwargs': {'username': 'voland.jos@gmail.com', 'password': 'josyka1994vpn'}}


keyboard_room = telebot.types.ReplyKeyboardMarkup(True, True)
keyboard_room.row('Создать комнату', 'Присоединиться')

keyboard_appr = telebot.types.ReplyKeyboardMarkup(True, True)
keyboard_appr.row('Отправить')

rooms = {}
room_owners = {}
room_players = {}
room_seekers = []

player_part = {}


def reverse_voice(file_path, room_num):
    print(file_path)
    init_ogg = AudioSegment.from_ogg(file_path)
    ogg_rev = init_ogg.reverse()
    ogg_rev.export('voices/{}_rev.mp3'.format(room_num), format='mp3')

    dur = len(ogg_rev)
    pt = int(dur/3500)+1
    rev_pts = []
    for i in range(0, pt+1):
        ogg_rev[i*int(dur/pt):(i + 1) * int(dur/pt)].export('voices/{}_rev{}.mp3'.format(room_num, i+1), format='mp3')
        rev_pts.append('{}_rev{}.mp3'.format(room_num, i+1))
    return rev_pts


def player_reverse(room_num):
    tks = []
    for pt in rooms[room_num]['audio']['pl_pts']:
        tr = AudioSegment.from_ogg(pt)
        tks.append(tr)
    res_tr = AudioSegment.empty()
    for i in range(0, len(tks)):
        res_tr = res_tr + tks[i]

    res_tr = res_tr.reverse()
    res_tr.export('voices/{}_pl_full.mp3'.format(room_num), format='mp3')
    return 'voices/{}_pl_full.mp3'.format(room_num)


def send_reverse(room_num, part, player_id):
    if room_num not in rooms.keys():
        return
    if rooms[room_num]['audio']['init'] == '':
        return
    fn = 'voices/{}_rev.mp3'.format(room_num) if part == 0 else 'voices/{}_rev{}.mp3'.format(room_num, part)
    vc = open(fn, 'rb')
    bot.send_audio(player_id, vc, performer='AJOP', title='Game {}'.format(room_num))


@bot.message_handler(commands=['start', 'help', 'newgame'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Это бот для игры в АПОЖ. Чтобы начать играть, создай комнату "
                                      "или присоединись к существующей!",
                     reply_markup=keyboard_room)


@bot.message_handler(commands=['exit'])
def room_exit(message):
    try:
        is_owner = message.chat.id in room_owners.keys()
        is_player = message.chat.id in room_players.keys()
        if not is_owner and not is_player:
            return
        else:
            rn = -1
            if is_owner:
                rn = room_owners[message.chat.id]
                player_id = rooms[rn]['players'][0] if len(rooms[rn]['players']) > 0 else -1
                bot.send_message(player_id, 'Ведущий вышел из комнаты. '
                                            'Можете создать новую комнату или присоединиться к другой',
                                 reply_markup=keyboard_room)
                del room_owners[message.chat.id]
                if player_id in room_players:
                    del room_players[player_id]
                if player_id in player_part:
                    del player_part[player_id]
            if is_player:
                rn = room_players[message.chat.id]
                owner_id = rooms[rn]['owner']
                bot.send_message(owner_id, 'Игрок вышел из комнаты. '
                                           'Можете создать новую комнату или присоединиться к другой',
                                 reply_markup=keyboard_room)
                del room_owners[owner_id]
                del room_players[message.chat.id]
                del player_part[message.chat.id]
            if rn in rooms:
                del rooms[rn]
            bot.send_message(message.chat.id, "Вы вышли из комнаты. Можете создать новую или присоединиться к другой",
                             reply_markup=keyboard_room)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)")



@bot.message_handler(func=lambda message: message.text in ['Создать комнату', 'Присоединиться'], content_types=['text'])
def room_handling(message):
    try:
        print(message.text)
        if message.chat.id in room_owners.keys() or message.chat.id in room_players.keys():
            rn = room_owners[message.chat.id] if message.chat.id in room_owners.keys() else room_players[message.chat.id]
            bot.send_message(message.chat.id, 'Вы уже находитесь в комнате {} в качестве ведущего. '
                                              'Введите /exit если хотите выйти.'.format(rn))
        if message.text == 'Создать комнату':
            rn = random.randint(100000, 999999)
            rooms[rn] = {'owner': message.chat.id, 'players': [], 'audio': {'init': ''}}
            room_owners[message.chat.id] = rn
            bot.send_message(message.chat.id, 'Комната {} создана. Перешлите её номер соигроку.'.format(rn))
            bot.send_message(message.chat.id, 'Вы выступите в роли ведущего. Пришлите песню аудиосообщением')
        elif message.text == 'Присоединиться':
            room_seekers.append(message.chat.id)
            bot.send_message(message.chat.id, 'Введите номер комнаты чтобы присоединиться')
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)")


@bot.message_handler(func=lambda message: message.text.isdigit() if message.text is not None else False,
                     content_types=['text'])
def room_connecting(message):
    try:
        if message.chat.id in room_seekers:
            rn = int(message.text)
            if rn not in rooms:
                bot.send_message(message.chat.id, 'Комнаты не существует!')
                return
            if len(rooms[rn]['players']) == 1:
                bot.send_message(message.chat.id, 'Комната заполнена!')
                return
            rooms[rn]['players'].append(message.chat.id)
            o_id = rooms[rn]['owner']
            room_seekers.remove(message.chat.id)
            room_players[message.chat.id] = rn
            bot.send_message(message.chat.id,
                             'Вы присоединились к комнате {}. Ждите перевернутую запись!'.format(rn))
            bot.send_message(o_id,
                             '{} присоединился(-лась)'.format(message.chat.username))
            if rooms[rn]['audio']['init'] != '':
                player_start_game(message.chat.id, rn)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)")


@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    try:
        if message.chat.id not in room_owners and message.chat.id in player_part:
            part = player_part[message.chat.id]
            file_info = bot.get_file(message.voice.file_id)
            file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path))
            rn = room_players[message.chat.id]
            fp = '{}_player{}.ogg'.format(rn, part)
            #open(fp, 'wb').write(file.content)
            resp = s3.upload_fileobj(file, S3_BUCKET, fp)
            keyboard_pappr_init = telebot.types.ReplyKeyboardMarkup(True, True)
            keyboard_pappr_init.row('Продолжить')
            bot.send_message(message.chat.id, 'Фантастика! Подтвердите запись или перезапишите её',
                             reply_markup=keyboard_pappr_init)

            owner_id = rooms[rn]['owner']
            bot.send_message(owner_id, 'Игрок записал {} часть(-ей)'.format(part))

        elif rooms[room_owners[message.chat.id]]['audio']['init'] == '':
            file_info = bot.get_file(message.voice.file_id)
            file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path))
            rn = room_owners[message.chat.id]
            fp = '{}_init.ogg'.format(rn)
            with io.BytesIO(file.content) as f:
                resp = s3.upload_fileobj(f, S3_BUCKET, fp)
            #rev_pts = reverse_voice(fp, rn)
            #rev_voice = open('{}_rev.mp3'.format(rn), 'rb')
            #rooms[rn]['audio']['rev_full'] = '{}_rev.mp3'.format(rn)
            #rooms[rn]['audio']['rev_pts'] = rev_pts
            #bot.send_audio(message.chat.id, rev_voice)
            bot.send_message(message.chat.id, 'Отправьте запись игрокам или перезапишите её',
                             reply_markup=keyboard_appr)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)" + str(e))


@bot.message_handler(func=lambda message: message.text in ['Отправить'], content_types=['text'])
def approve_voice(message):
    try:
        print(message.text)
        if message.text == 'Отправить' and message.chat.id in room_owners:
            rn = room_owners[message.chat.id]
            fp = 'voices/{}_init.ogg'.format(rn)
            rooms[room_owners[message.chat.id]]['audio']['init'] = fp
            bot.send_message(message.chat.id, 'Ожидайте, пока игрок запишет свою версию...')
            if len(rooms[rn]['players']) > 0:
                player_start_game(rooms[rn]['players'][0], rn)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)")


def player_start_game(player_id, room_num):
    keyboard_pappr_init = telebot.types.ReplyKeyboardMarkup(True, True)
    keyboard_pappr_init.row('Продолжить')
    bot.send_message(player_id, 'Игра начинается!. Прослушайте запись целиком'
                                ', и нажмите продолжить, чтобы начать запись по кусочкам!',
                     reply_markup=keyboard_pappr_init)
    send_reverse(room_num, 0, player_id)
    player_part[player_id] = 0
    rooms[room_num]['audio']['pl_pts'] = []


@bot.message_handler(func=lambda message: message.text in ['Продолжить'], content_types=['text'])
def player_recording(message):
    try:
        print(message.text)
        if message.text == 'Продолжить':
            if message.chat.id not in player_part:
                return
            p_id = message.chat.id
            rn = room_players[message.chat.id]
            rev_pts = rooms[rn]['audio']['rev_pts']
            if player_part[p_id] > 0:
                rooms[rn]['audio']['pl_pts'].append('voices/{}_player{}.ogg'.format(rn, player_part[p_id]))

            player_part[p_id] = player_part[p_id] + 1
            if player_part[p_id] <= len(rev_pts):
                bot.send_message(p_id,
                                 'Прослушайте отрывок'
                                 ' и постарайтесь записать максимально похоже! ({}/{})'.format(player_part[p_id],
                                                                                               len(rev_pts)))
                send_reverse(rn, player_part[p_id], p_id)
            elif player_part[p_id] > len(rev_pts):
                bot.send_message(p_id,
                                 'Прослушайте, что получилось и попытайтелсь угадать! (Напишите: "Ответ: <название>)')
                res_pl = player_reverse(rn)
                vc = open(res_pl, 'rb')
                bot.send_audio(p_id, vc, performer='AJOP', title='Game {}'.format(rn))
                o_id = rooms[rn]['owner']
                bot.send_message(o_id,
                                 'Вот что получилось у игрока! Дождитесь его догадки...')
                vc = open(res_pl, 'rb')
                bot.send_audio(o_id, vc, performer='AJOP', title='Game {}'.format(rn))
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)")


@bot.message_handler(func=lambda message: message.text.lower().startswith('ответ'))
def finishing_ans(message):
    try:
        print(message.text)
        if message.chat.id in room_players:
            rn = room_players[message.chat.id]
            o_id = rooms[rn]['owner']
            keyboard_fin = telebot.types.ReplyKeyboardMarkup(True, True)
            keyboard_fin.row('Отправить оригинал')
            bot.send_message(o_id, message.text, reply_markup=keyboard_fin)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)")


@bot.message_handler(func=lambda message: message.text.lower() in ['Отправить оригинал'])
def finish_orig(message):
    try:
        if message.chat.id in room_owners:
            rn = room_owners[message.chat.id]
            player_id = rooms[rn]['players'][0]

            fn = rooms[rn]['audio']['init']
            init_tr = open(fn, 'rb')
            bot.send_audio(player_id, init_tr)

            bot.send_message(message.chat.id, 'Игра закончена. Введите /newgame чтобы начать новую.')
            bot.send_message(player_id, 'Игра закончена. Введите /newgame чтобы начать новую.')

            del rooms[rn]
            del room_owners[message.chat.id]
            del room_players[player_id]
            del player_part[player_id]
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Произошла ошибка. Советуем начать новую игру - /newgame)")


@app.route('/', methods=['GET', 'HEAD'])
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://sheltered-meadow-12656.herokuapp.com/' + secret)
    return "!", 200


@app.route('/' + secret, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(flask.request.stream.read().decode("utf-8"))])
    return "!", 200


if __name__ == '__main__':
    app.debug = True
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
