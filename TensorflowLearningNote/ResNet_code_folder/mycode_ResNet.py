#_*_coding:utf-8_*_
import time
import cv2
import os
import numpy as np
from sklearn.utils import shuffle
from keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from keras.models import Sequential
from keras.layers import Conv2D, MaxPooling2D, Dense, Flatten, Dropout, ZeroPadding2D, AveragePooling2D
from keras.optimizers import SGD
from keras.layers import merge, Concatenate, Add
from keras.layers.core import Activation
from keras.layers.normalization import BatchNormalization
from keras.utils.vis_utils import plot_model
from sklearn.preprocessing import LabelEncoder
from keras.utils import to_categorical
import matplotlib as mpl
from keras.layers import Input
from keras.models import Model

mpl.use('Agg')

import matplotlib.pyplot as plt



LABEL_MATCH ={
    'bus':0,
    'dinosaurs':1,
    'elephants':2,
    'flowers':3,
    'horse':4,
}

# read data way1
def read_image(imagepath, target_size, class_name):
    data_list, label_list = [], []
    for image_name in os.listdir(imagepath):
        tmp_path = os.path.join(imagepath, image_name)
        img = cv2.imread(tmp_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.resize(img, target_size)
        data_list.append(img)
        label = LABEL_MATCH[class_name]
        label_list.append(label)
    return data_list, label_list



def get_data(train_folder, target_size):
    data, labels = [], []
    for class_name in os.listdir(train_folder):
        tmp_path = os.path.join(train_folder, class_name)
        tmp_data, tmp_label = read_image(tmp_path, target_size, class_name)
        data.extend(tmp_data)
        labels.extend(tmp_label)

    labels = to_categorical(labels)
    data, labels = np.array(data, dtype='float'), np.array(labels)
    data /= 255.0
    data, labels = shuffle(data, labels, random_state=32)
    data_nums = data.shape[0]
    # print(data.shape, labels, data.shape[0], type(data.shape[0]))
    return data, labels, data_nums



# read data way2
def generate_data(train_folder, test_folder, target_size, batch_size=32, class_mode='categorical'):
    train_datagen = ImageDataGenerator(rescale=1./255,)
    #  shear_range=0.2, zoom_range=0.2)
    train_data = train_datagen.flow_from_directory(
        train_folder,
        target_size = target_size,
        batch_size = batch_size,
        class_mode = class_mode,
        color_mode='grayscale'
        )

    validation_datagen = ImageDataGenerator(rescale=1./255)
    valid_data = validation_datagen.flow_from_directory(
        test_folder,
        target_size = target_size,
        batch_size = batch_size,
        class_mode = class_mode,
        color_mode='grayscale'
        )

    return train_data, valid_data


def identity_block(input_tensor, nb_filter, kernel_size=(3, 3)):
    '''
        直接相加，并不需要 1*1 卷积
        nb_filter：卷积核个数，需要按顺序指定3个，例如（64,64,256）
    '''
    nb_filter1, nb_filter2, nb_filter3 = nb_filter
    out = Conv2D(nb_filter1, kernel_size=(1, 1))(input_tensor)
    out = BatchNormalization()(out)
    out = Activation('relu')(out)

    out = Conv2D(nb_filter2, kernel_size, padding='same')(out)
    out = BatchNormalization()(out)
    out = Activation('relu')(out)

    out = Conv2D(nb_filter3, kernel_size=(1, 1))(out)
    out = BatchNormalization()(out)

    out = Add()([out, input_tensor])
    #out = Concatenate()([out, input_tensor])
    out = Activation('relu')(out)
    return out


def conv_block(input_tensor, nb_filter, kernel_size=(3, 3)):
    nb_filter1, nb_filter2, nb_filter3 = nb_filter

    out = Conv2D(nb_filter1, kernel_size=(1, 1))(input_tensor)
    out = BatchNormalization()(out)
    out = Activation('relu')(out)

    out = Conv2D(nb_filter2, kernel_size, padding='same')(out)
    out = BatchNormalization()(out)
    out = Activation('relu')(out)

    out = Conv2D(nb_filter3, kernel_size=(1, 1))(out)
    out = BatchNormalization()(out)

    x = Conv2D(nb_filter3, kernel_size=(1, 1))(input_tensor)
    x = BatchNormalization()(x)

    out = Add()([out, x])
    #out = Concatenate()([out, x])
    out = Activation('relu')(out)

    return out


def build_model(input_shape, classes):
    inp = Input(input_shape)
    out = ZeroPadding2D((3, 3))(inp)

    # stage 1
    out = Conv2D(filters=64, kernel_size=(7, 7), subsample=(2, 2))(out)
    out = BatchNormalization()(out)
    out = Activation('relu')(out)
    out = MaxPooling2D(pool_size=(3, 3), strides=(2, 2))(out)

    # stage 2
    out = conv_block(out, [64, 64, 256])
    out = identity_block(out, [64, 64, 256])
    out = identity_block(out, [64, 64, 256])

    # stage 3
    out = conv_block(out, [128, 128, 512])
    out = identity_block(out, [128, 128, 512])
    out = identity_block(out, [128, 128, 512])
    out = identity_block(out, [128, 128, 512])

    # stage 4
    out = conv_block(out, [256, 256, 1024])
    out = identity_block(out, [256, 256, 1024])
    out = identity_block(out, [256, 256, 1024])
    out = identity_block(out, [256, 256, 1024])
    out = identity_block(out, [256, 256, 1024])
    out = identity_block(out, [256, 256, 1024])

    # stage 5
    out = conv_block(out, [512, 512, 2048])
    out = identity_block(out, [512, 512, 2048])
    out = identity_block(out, [512, 512, 2048])

    out = AveragePooling2D(pool_size=(7, 7))(out)
    out = Flatten()(out)

    out = Dense(classes, activation='softmax')(out)

    model = Model(inp, out)
    model.summary()
    return model


def train_model_with_generator(train_data, valid_data, train_nums, valid_nums, epochs, batch_size, input_shape, classes):
    model = build_model(input_shape, classes)
    # 优化器
    sgd = SGD(lr=0.05, decay=1e-6, momentum=0.9, nesterov=True)
    model.compile(optimizer='rmsprop', loss='categorical_crossentropy',
        metrics=['accuracy'])
    history = model.fit_generator(train_data, 
        #samples_per_epoch=train_nums//batch_size,
        samples_per_epoch=80,
        nb_epoch=epochs,
        validation_data=valid_data,
        #nb_val_samples=valid_nums//batch_size
        nb_val_samples=20)

    return history


def train_model_with_data(data, labels, batch_size, epochs, input_shape, classes):
    if np.ndim(data) < 4:
        data = np.expand_dims(data, 3)
    train_data, test_data, train_labels, test_labels = train_test_split(data, labels, test_size=0.2, random_state=12)
    model = build_model(input_shape, classes)
    model.compile(optimizer='rmsprop', loss='categorical_crossentropy',
        metrics=['accuracy'])
    history = model.fit(train_data, train_labels,
        batch_size=batch_size,
        epochs=epochs,
        validation_split=0.2)

    score = model.evaluate(test_data, test_labels, batch_size=batch_size)
    print('loss accuracy is %s'%score)

    return history


def plot_train_Loss_Acc(history, save_path=r'/data/lebron/vggnetloss.jpg'):
    plt.figure(21)
    plt.subplot(211)
    plt.plot(history.history['acc'], 'ro')
    plt.plot(history.history['val_acc'], 'b')
    plt.title('Training and Validation accuracy')
    plt.ylabel('Accuracy')
    plt.xlabel('Epochs')
    plt.legend(['Train acc', 'val acc'], loc='upper left')

    plt.subplot(212)
    plt.plot(history.history['loss'], 'ro')
    plt.plot(history.history['val_loss'], 'b')
    plt.title('Training and Validation Loss')
    plt.ylabel('Loss')
    plt.xlabel('Epochs')
    plt.legend(['Train loss', 'val loss'], loc='upper left')
    plt.tight_layout()
    plt.savefig(save_path)



def main(flags=True):
    train_folder = r'/data/lebron/data5/mytrain'
    test_folder = r'/data/lebron/data5/mytest'
    target_size = (224, 224)
    input_shape, classes = (224, 224, 1), 5
    batch_size = 8
    epochs = 100

    if flags:
        all_folder = r'/data/lebron/data5/all_data'
        data, labels, data_nums = get_data(train_folder, target_size)
        history = train_model_with_data(data, labels, batch_size, epochs, input_shape, classes)
        plot_train_Loss_Acc(history)

    else:
        train_nums, valid_nums = 400, 100
        train_data, valid_data = generate_data(train_folder, test_folder, target_size, batch_size)
        history = train_model_with_generator(train_data, valid_data, train_nums, valid_nums, epochs, batch_size, input_shape, classes)
        plot_train_Loss_Acc(history)
        
if __name__ == '__main__':
    start_time = time.time()
    # main(True)
    input_shape, classes = (224, 224, 3), 5
    build_model(input_shape, classes)
    print('all time is %s'%(time.time() - start_time))
