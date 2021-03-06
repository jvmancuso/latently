#!/usr/bin/env python3

# Given an image (possibly generated by the GAN)
# this scripts tries to recover its latent vector.
#
# The algorithm is based on the ICLR 17 workshop paper:
# https://openreview.net/forum?id=HJC88BzFl
# Precise Recovery of Latent Vectors from Generative Adversarial Networks
# by Zachary C. Lipton, and Subarna Tripathi

# It requires:
# - a starting image, ./interpolation_from_start/foo_00.png
# - its latent vector (optional) ./interpolation_from_start/zp_start.npy

import argparse
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from PIL import Image


def main(args):
    truncation = args.truncation
    # Choose a random starting point
    zp = tf.Variable(truncation * tf.truncated_normal([len(args.images), 128]))
    # Or if we know the original latent vector, we can start from it
    # start_zp = np.load(folder + "zp_start.npy")
    # zzp = np.empty((1,512))
    # zzp[0] = start_zp
    # zp = tf.Variable(zzp, dtype=tf.float32)

    # Load the image for which we want to recover the latent vector
    # and crete an appropriate tensor for it
    print("Loading images...")
    arrays = []
    for img_name in args.images:
        img = Image.open("{}/{}".format(args.source_dir, img_name))
        img = img.resize((512, 512), Image.LANCZOS)
        img_arr = np.expand_dims(np.array(img), axis=0)
        arrays.append(img_arr / 255.)
    img_np = np.concatenate(arrays, axis=0)
    fz = tf.Variable(img_np, tf.float32)
    batch_size = len(args.images)
    y_index = tf.random_uniform([batch_size], maxval=1000, dtype=tf.int32)
    y = tf.Variable(tf.one_hot(y_index, 1000))

    inputs = {k: tf.placeholder(v.dtype, v.get_shape().as_list(), k)
          for k, v in module.get_input_info_dict().iteritems()}

    input_z = inputs['z']
    input_y = inputs['y']
    input_trunc = inputs['truncation']

    dim_z = input_z.shape.as_list()[1]
    vocab_size = input_y.shape.as_list()[1]

    def truncated_z_sample(batch_size, truncation=1., seed=None):
        state = None if seed is None else np.random.RandomState(seed)
        values = truncnorm.rvs(-2, 2, size=(batch_size, dim_z), random_state=state)
        return truncation * values

    def one_hot(index, vocab_size=vocab_size):
        index = np.asarray(index)
        if len(index.shape) == 0:
            index = np.asarray([index])
        assert len(index.shape) == 1
        num = index.shape[0]
        output = np.zeros((num, vocab_size), dtype=np.float32)
        output[np.arange(num), index] = 1
        return output

    def one_hot_if_needed(label, vocab_size=vocab_size):
        label = np.asarray(label)
        if len(label.shape) <= 1:
            label = one_hot(label, vocab_size)
        assert len(label.shape) == 2
        return label

    # Define the optimization problem
    print("Loading generator...")
    generator = hub.Module("https://tfhub.dev/deepmind/biggan-512/2")
    print("Generating image from random latent vector...")
    fzp = generator()
    loss = tf.losses.mean_squared_error(labels=fz, predictions=fzp)

    # Decayed gradient descent
    global_step = tf.Variable(0, trainable=False)
    learning_rate = tf.train.exponential_decay(args.init_lr,
                                               global_step,
                                               args.decay_steps,
                                               args.decay_rate)
    opt = tf.train.GradientDescentOptimizer(learning_rate)
    # Optimize on the variable zp
    train = opt.minimize(loss, var_list=[zp, y], global_step=global_step)

    sess = tf.Session()
    sess.run(tf.global_variables_initializer())
    for i in range(args.iters): # Use more iterations (10000)
        # If we know the original latent vector, we can also compute
        # how far the recovered vector is from it
        _, loss_value, zp_val, eta = sess.run((train, loss, zp, y, learning_rate))
        print("%03d) eta=%03f, loss = %f" % (i, eta, loss_value))
    # Save the recovered latent vector
    zp_val, y_val = sess.run(zp, y)
    for ix, img_name in enumerate(args.images):
        np.save("{}/{}.npy".format(args.dest_dir, img_name[:-4]), zp_val[ix])

    # Print out the corresponding image out of the recovered
    # latent vector
    imgs = sess.run(generator({z: zp_val, y: y_val}))
    imgs = (imgs * 255).astype(np.uint8)
    Image.fromarray(imgs[0]).save("{}/{}.recv.jpg".format(args.dest_dir, image_name[:-4]))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="recovering latent vectors of images")
    parser.add_argument('-I', '--images', type=str, nargs="+",
                        help="source images for which to recover vectors")
    parser.add_argument('-S', '--source-dir', type=str, default="source_images",
                        help="directory containing source images")
    parser.add_argument('-D', '--dest-dir', type=str, default="latent_vectors",
                        help="directory to store recovered latent vectors")

    parser.add_argument('-T', '--truncation', type=float, default=.5,
                        help="BigGAN truncation factor")

    parser.add_argument('-i', '--iters', type=int, default=10000,
                        help="number of iterations of gradient descent")
    parser.add_argument('-l', '--init-lr', type=float, default=.99,
                        help="inital learning rate")
    parser.add_argument('-ds', '--decay-steps', type=int, default=10000,
                        help="number of steps to decay learning rate over")
    parser.add_argument('-dr', '--decay-rate', type=float, default=0.005,
                        help="rate of decay for learing rate")

    args = parser.parse_args()

    main(args)
