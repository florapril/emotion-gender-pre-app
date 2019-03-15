# emotion-gender-pre-app
mini-project from course

## Function/Features
Receive a photo or URL of a photo containing human faces from users through **Telegram**. After the user chooses to predict emotion/gender, the system replies the user with the input image plus predictions of emotion/genders of faces.

## Machine Learning Task
Pre-trained models from https://github.com/oarriaga/face_classification are used in this project.

## Instructions on how to run the programs
First, make sure the redis-server is running. Then in the terminal, type the following command to run them. 
```
python bot.py
python download_image.py 3
python predict.py 3
```
Note: the number 3 in the end means the number of processes, which can be changed according to needs.

## Diagram of the System
![image](https://github.com/florapril/emotion-gender-pre-app/blob/master/Diagram%20of%20the%20System%20Architecture.png?raw=true)
