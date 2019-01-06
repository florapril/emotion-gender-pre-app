import logging
from redis import StrictRedis
import json
import requests
from PIL import Image
import imagehash
import telepot
import base64
from io import BytesIO
from multiprocessing import Process
import sys


logging.basicConfig(level=logging.INFO)

# use redis for caching and message queue
r = StrictRedis(host='localhost', port=6379)

# download image from file id or URL and return error
def download(image_link, image_file):
    try:
        if image_link.startswith('http'):
            image_data = requests.get(image_link).content
            with open(image_file, 'wb') as outfile:
                outfile.write(image_data)
            error = None
            logging.info('Download photo from URL successfully.')
        else:
            bot.download_file(image_link, image_file)
            error = None
            logging.info('Download photo from file_id successfully.')
    except Exception as e:
        logging.info('Error: {}'.format(e))
        error = 'Unable to download the photo. Please check the photo or the url.'
    return error


# keep popping messages from message queue 'download'
# i is the process identifier
def process(i):
    while True:
        item = r.blpop('download')
        receive_content = json.loads(item[1].decode())
        logging.info('content: {}'.format(receive_content))

        image_file = '{}download_{}.jpg'.format(i, receive_content['chat_id'])

        # call function download
        download_error = download(receive_content['image_link'], image_file)

        # if there is no download error, check whether the image is in cache
        # if it is, get the cached prediction and push it as well as chat id into message queue 'prediction'
        # if not, push chat id, choice of prediction and downloaded image into message queue 'image'
        if download_error is None:
            try:
                image = Image.open(image_file)

                # turn the image into hash, and check the cache
                image_hash = str(imagehash.average_hash(image))
                cached = r.get(str((image_hash, receive_content['pre'])))

                if cached is not None:
                    send_content = {'chat_id': receive_content['chat_id'], 'encoded_image': cached.decode()}
                    r.rpush('prediction', json.dumps(send_content))

                else:
                    buffered = BytesIO()
                    image.save(buffered, format='JPEG')
                    encoded_image = base64.b64encode(buffered.getvalue())
                    send_content = {'chat_id': receive_content['chat_id'], 'pre': receive_content['pre'],
                                    'encoded_image': encoded_image.decode()}
                    r.rpush('image', json.dumps(send_content))

            # catch possible error, push the error and chat id into message queue 'prediction'
            except Exception as e:
                logging.info('Error: {}'.format(e))
                send_content = {'chat_id': receive_content['chat_id'],
                                'error': 'Unable to open the photo. Please check the photo or the url.'}
                r.rpush('prediction', json.dumps(send_content))

        # if there is download error, push chat id and error into message queue 'prediction'
        else:
            send_content = {'chat_id': receive_content['chat_id'], 'error': download_error}
            r.rpush('prediction', json.dumps(send_content))

if __name__ == '__main__':

    bot = telepot.Bot('641116949:AAEHvkpiPlBgWv6yHJfG3yE4AywTSfKdvdA')

    # n is the number of processes, which can be changed according to needs
    n = sys.argv[1]
    processes = []
    for i in range(int(n)):
        p = Process(target=process, args=(i,))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()