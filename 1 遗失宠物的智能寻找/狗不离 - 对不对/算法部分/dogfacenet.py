from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf

import os
import numpy as np
import skimage as sk
import matplotlib.pyplot as plt
import tensorflow.keras.backend as K
from online_training import *

PATH        = '../data/dogfacenet/'
PATH_SAVE   = '../output/history/'
PATH_MODEL  = '../output/model/'
SIZE        = (224,224,3) 
TEST_SPLIT  = 0.1

START_EPOCH = 0 
NBOF_EPOCHS = 250 
HIGH_LEVEL  = True 
STEPS_PER_EPOCH = 300
VALIDATION_STEPS = 30 



filenames = np.empty(0)
labels = np.empty(0)
idx = 0
for root,dirs,files in os.walk(PATH):
    if len(files)>1:
        for i in range(len(files)):
            files[i] = root + '/' + files[i]
        filenames = np.append(filenames,files)
        labels = np.append(labels,np.ones(len(files))*idx)
        idx += 1
assert len(labels)!=0, '[Error] No data provided.'

print('Done.')

print('Total number of imported pictures: {:d}'.format(len(labels)))

nbof_classes = len(np.unique(labels))
print('Total number of classes: {:d}'.format(nbof_classes))

nbof_test = int(TEST_SPLIT*nbof_classes)

keep_test = np.less(labels,nbof_test)
keep_train = np.logical_not(keep_test)

filenames_test = filenames[keep_test]
labels_test = labels[keep_test]

filenames_train = filenames[keep_train]
labels_train = labels[keep_train]

print("Number of training data: " + str(len(filenames_train)))
print("Number of training classes: " + str(nbof_classes-nbof_test))
print("Number of testing data: " + str(len(filenames_test)))
print("Number of testing classes: " + str(nbof_test))
n.

alpha = 0.3
def triplet(y_true,y_pred):
    
    a = y_pred[0::3]
    p = y_pred[1::3]
    n = y_pred[2::3]
    
    ap = K.sum(K.square(a-p),-1)
    an = K.sum(K.square(a-n),-1)

    return K.sum(tf.nn.relu(ap - an + alpha))

def triplet_acc(y_true,y_pred):
    a = y_pred[0::3]
    p = y_pred[1::3]
    n = y_pred[2::3]
    
    ap = K.sum(K.square(a-p),-1)
    an = K.sum(K.square(a-n),-1)
    
    return K.less(ap+alpha,an)

from tensorflow.keras import Model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Add, GlobalAveragePooling2D, DepthwiseConv2D
from tensorflow.keras.layers import Activation, Dropout, Flatten, Dense, Lambda, BatchNormalization

print('Defining model {:s} ...'.format(NET_NAME))

emb_size = 32

inputs = Input(shape=SIZE)

x = Conv2D(16, (7, 7), (2, 2), use_bias=False, activation='relu', padding='same')(inputs)
x = BatchNormalization()(x)
x = MaxPooling2D((3,3))(x)

for layer in [16,32,64,128,512]:

    x = Conv2D(layer, (3, 3), strides=(2,2), use_bias=False, activation='relu', padding='same')(x)
    r = BatchNormalization()(x)
    
    x = Conv2D(layer, (3, 3), use_bias=False, activation='relu', padding='same')(r)
    x = BatchNormalization()(x)
    r = Add()([r,x])
    
    x = Conv2D(layer, (3, 3), use_bias=False, activation='relu', padding='same')(r)
    x = BatchNormalization()(x)
    x = Add()([r,x])
    

x = GlobalAveragePooling2D()(x)
x = Flatten()(x)
x = Dropout(0.5)(x)
x = Dense(emb_size, use_bias=False)(x)
outputs = Lambda(lambda x: tf.nn.l2_normalize(x,axis=-1))(x)

model = tf.keras.Model(inputs,outputs)

model.compile(loss=triplet,
            optimizer='adam',
            metrics=[triplet_acc])

print('Done.')

print(model.summary())

histories = []
crt_loss = 0.6
crt_acc = 0
batch_size = 3*10
nbof_subclasses = 40

if not os.path.isdir(PATH_MODEL):
    os.makedirs(PATH_MODEL)
if not os.path.isdir(PATH_SAVE):
    os.makedirs(PATH_SAVE)

for images_batch,labels_batch in online_adaptive_hard_image_generator(
    filenames_train,
    labels_train,
    model,
    crt_acc,
    batch_size,
    nbof_subclasses=nbof_subclasses):
    h = model.train_on_batch(images_batch,labels_batch)
    break


for i in range(START_EPOCH,START_EPOCH+NBOF_EPOCHS):
    print("Beginning epoch number: "+str(i))

    hard_triplet_ratio = np.exp(-crt_loss * 10 / batch_size)
    nbof_hard_triplets = int(batch_size//3 * hard_triplet_ratio)
    
    print("Current hard triplet ratio: " + str(hard_triplet_ratio))
    
    histories += [model.fit_generator(
        online_adaptive_hard_image_generator(filenames_train,labels_train,model,crt_loss,batch_size,nbof_subclasses=nbof_subclasses),
        steps_per_epoch=STEPS_PER_EPOCH,
        epochs=1,
        validation_data=image_generator(filenames_test,labels_test,batch_size,use_aug=False),
        validation_steps=VALIDATION_STEPS)]
    
    crt_loss = histories[-1].history['loss'][0]
    crt_acc = histories[-1].history['triplet_acc'][0]

    model.save('{:s}{:s}.{:d}.h5'.format(PATH_MODEL,NET_NAME,i))

    loss = np.empty(0)
    val_loss = np.empty(0)
    acc = np.empty(0)
    val_acc = np.empty(0)

    for history in histories:
        loss = np.append(loss,history.history['loss'])
        val_loss = np.append(val_loss,history.history['val_loss'])
        acc = np.append(acc,history.history['triplet_acc'])
        val_acc = np.append(val_acc,history.history['val_triplet_acc'])

    history_ = np.array([loss,val_loss,acc,val_acc])
    np.save('{:s}{:s}.{:d}.npy'.format(PATH_SAVE,NET_NAME,i),history_)

