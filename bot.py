import logging
from redis import StrictRedis
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardButton, InlineKeyboardMarkup
import json
import base64
import threading

logging.basicConfig(level=logging.INFO)

# use redis for caching and message queue
r = StrictRedis('localhost', port=6379)

# a keyboard in which user can choose to predict emotion or gender of faces from a photo
def return_keyboard(msg_id):
    my_inline_keyboard = [[
        InlineKeyboardButton(text='emotion',
                             callback_data=json.dumps({'msg_id': msg_id, 'prediction': 'emotion'})),
        InlineKeyboardButton(text='gender',
                             callback_data=json.dumps({'msg_id': msg_id, 'prediction': 'gender'})),
    ]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=my_inline_keyboard)
    return keyboard

# keep receiving messages from users
def receive(msg):
    data = msg.get('data', None)
    photo = msg.get('photo', None)
    text = msg.get('text', None)
    document = msg.get('document', None)

    # if receiving a photo, cache the chat id, msg id and file id, return the choice keyboard to user
    if photo is not None:
        chat_id = msg['chat']['id']
        msg_id = msg['message_id']
        logging.info('Receive photo {} from {}.'.format(msg_id, chat_id))
        r.set(str((chat_id, msg_id)), msg['photo'][-1]['file_id'], ex=1000)
        bot.sendMessage(chat_id, "What do you want to predict?", reply_markup=return_keyboard(msg_id))

    # if receiving text, check if it is a URL
    # if it is, cache the chat id, msg id and URL, return the choice keyboard to user
    # if not, send a hint to user
    elif text is not None:
        chat_id = msg['chat']['id']
        if text.startswith('http'):
            msg_id = msg['message_id']
            logging.info('Receive URL {} from {}.'.format(text, chat_id))
            r.set(str((chat_id, msg_id)), text, ex=1000)
            bot.sendMessage(chat_id, 'What do you want to predict?', reply_markup=return_keyboard(msg_id))
        else:
            bot.sendMessage(chat_id, 'I can predict the emotion/gender of human faces. '
                                     'Please send me a photo or the URL of a photo ^ ^')

    # if receiving data, get msg id and choice of prediction from data
    # check whether the image link (file id/URL) is in cache according to chat id and msg id
    # if it is, push chat id, choice of prediction, image link into message queue 'download'
    # if not, send 'Sorry, there is an error. Please send the photo again.' to user
    elif data is not None:
        chat_id = msg['message']['chat']['id']
        logging.info("Receive prediction kind: {}".format(data))
        dict_data = json.loads(data)
        msg_id = dict_data['msg_id']
        image_link = r.get(str((chat_id, msg_id)))
        if image_link is not None:
            send_content = {'chat_id': chat_id, 'pre': dict_data['prediction'],
                            'image_link': image_link.decode()}
            success = r.rpush('download', json.dumps(send_content))
            logging.info('Push successfully? {}'.format(success))
            bot.sendMessage(chat_id, 'Please wait a moment...')
        else:
            bot.sendMessage(chat_id, 'Sorry, there is an error. Please send the photo again.')

    # if users send photo through 'Send File' way, ask them to change the way
    elif document is not None:
        chat_id = msg['chat']['id']
        logging.info('Receive document from {}.'.format(chat_id))
        bot.sendMessage(chat_id, "Pleas send the photo through 'Send Photo' rather than 'Send File'.")

    else:
        chat_id = msg['chat']['id']
        bot.sendMessage(chat_id, 'I can predict the emotion/gender of human faces. '
                                 'Please send me a photo or the URL of a photo ^ ^')

# keep popping message from message queue 'prediction', and send result to user
def reply():
    while True:
        item = r.blpop('prediction')
        receive_content = json.loads(item[1].decode())
        logging.info('Receive after_pre_image: {}'.format(receive_content))

        # check whether there is error in message
        error = receive_content.get('error', None)

        # if there is no error, send prediction result to user
        if error is None:

            # check whether detect faces in the photo
            # if detecting faces, send the image with prediction result to user
            # if not, ask user to send a photo with clear faces again
            if receive_content['encoded_image'] is not None:
                image_data = base64.b64decode(receive_content['encoded_image'])
                image_file = 'result_{}.jpg'.format(receive_content['chat_id'])
                with open(image_file, 'wb') as outfile:
                    outfile.write(image_data)
                bot.sendPhoto(receive_content['chat_id'], open(image_file, 'rb'))
            else:
                bot.sendMessage(receive_content['chat_id'], 'Sorry! Can not detect human faces. '
                                                            'Please send photo with clear human faces.')

        # if there is error, send the error to user
        else:
            bot.sendMessage(receive_content['chat_id'], receive_content['error'])


if __name__ == '__main__':
    bot = telepot.Bot('641116949:AAEHvkpiPlBgWv6yHJfG3yE4AywTSfKdvdA')

    # thread for replying user
    threading.Thread(target=reply).start()

    # thread for listening user
    MessageLoop(bot, receive).run_as_thread()

    main_thread = threading.main_thread()
    for t in threading.enumerate():
        if t != main_thread:
            t.join()