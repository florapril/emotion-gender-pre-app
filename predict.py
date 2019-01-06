import logging
from redis import StrictRedis
import json
import base64
from predictions.emotion import predict_emotion
from predictions.gender import predict_gender
from PIL import Image
import imagehash
from io import BytesIO
from PIL import ImageFile
from multiprocessing import Process
import sys


logging.basicConfig(level=logging.INFO)

# use redis for caching and message queue
r = StrictRedis(host='localhost', port=6379)

# use pre-trained model to predict emotion or gender
# i is the identifier of process
def model(i, pre, chat_id, image_file):
    if pre == 'emotion':
        number = predict_emotion(i, chat_id, image_file)
    elif pre == 'gender':
        number = predict_gender(i, chat_id, image_file)
    else:
        number = 0
    return number

# keep popping message from message queue 'image' and do prediction
def predict(i):
    while True:
        item = r.blpop('image')
        receive_content = json.loads(item[1].decode())
        logging.info('content: {}'.format(receive_content))

        image_data = base64.b64decode(receive_content['encoded_image'])
        image_file = '{}before_pre_{}.jpg'.format(i, receive_content['chat_id'])
        with open(image_file, 'wb') as outfile:
            outfile.write(image_data)

        # call function model, return the number of detected faces
        number_face = model(i, receive_content['pre'], receive_content['chat_id'], image_file)

        if number_face > 0:
            pre_image = Image.open('{}after_pre_{}.jpg'.format(i, receive_content['chat_id']))
            buffered = BytesIO()
            pre_image.save(buffered, format='JPEG')
            encoded_pre_image = base64.b64encode(buffered.getvalue())
            send_content = {'chat_id': receive_content['chat_id'], 'encoded_image': encoded_pre_image.decode()}
            logging.info('precontent: {}'.format(send_content))
            r.rpush('prediction', json.dumps(send_content))
        else:
            send_content = {'chat_id': receive_content['chat_id'], 'encoded_image': None}
            r.rpush('prediction', json.dumps(send_content))

        # push prediction result into message queue 'image' and cache
        image = Image.open(image_file)
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        image_hash = str(imagehash.average_hash(image))
        r.set(str((image_hash, receive_content['pre'])), send_content['encoded_image'], ex=1000)

if __name__ == '__main__':

    # n is the number of processes, which can be changed
    n = sys.argv[1]
    processes = []
    for i in range(int(n)):
        p = Process(target=predict, args=(i, ))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()