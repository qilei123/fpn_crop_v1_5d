# --------------------------------------------------------
# Deformable Convolutional Networks
# Copyright (c) 2017 Microsoft
# Licensed under The MIT License [see LICENSE for details]
# Written by Yuwen Xiong
# --------------------------------------------------------

import numpy as np
import os
import cv2
import random
from PIL import Image
from bbox.bbox_transform import clip_boxes
from math import floor

# TODO: This two functions should be merged with individual data loader
def get_image(roidb, config):
    """
    preprocess image and return processed roidb
    :param roidb: a list of roidb
    :return: list of img as in mxnet format
    roidb add new item['im_info']
    0 --- x (width, second dim of im)
    |
    y (height, first dim of im)
    """
    num_images = len(roidb)
    processed_ims = []
    processed_roidb = []
    for i in range(num_images):
        roi_rec = roidb[i]
        assert os.path.exists(roi_rec['image']), '%s does not exist'.format(roi_rec['image'])
        im = cv2.imread(roi_rec['image'], cv2.IMREAD_COLOR|cv2.IMREAD_IGNORE_ORIENTATION)
        if roidb[i]['flipped']:
            im = im[:, ::-1, :]
        new_rec = roi_rec.copy()
        scale_ind = random.randrange(len(config.SCALES))
        target_size = config.SCALES[scale_ind][0]
        max_size = config.SCALES[scale_ind][1]
        im, im_scale = resize(im, target_size, max_size, stride=config.network.IMAGE_STRIDE)
        im_tensor = transform(im, config.network.PIXEL_MEANS)
        processed_ims.append(im_tensor)
        im_info = [im_tensor.shape[2], im_tensor.shape[3], im_scale]
        new_rec['boxes'] = clip_boxes(np.round(roi_rec['boxes'].copy() * im_scale), im_info[:2])
        new_rec['im_info'] = im_info
        processed_roidb.append(new_rec)
    return processed_ims, processed_roidb

def compute_iou(rec1, rec2):
	"""
	computing IoU
	:param rec1: (y0, x0, y1, x1), which reflects
			(top, left, bottom, right)
	:param rec2: (y0, x0, y1, x1)
	:return: scala value of IoU
	"""
	# computing area of each rectangles
	S_rec1 = (rec1[2] - rec1[0]) * (rec1[3] - rec1[1])
	S_rec2 = (rec2[2] - rec2[0]) * (rec2[3] - rec2[1])

	# computing the sum_area
	sum_area = S_rec1 + S_rec2

	# find the each edge of intersect rectangle
	left_line = max(rec1[1], rec2[1])
	right_line = min(rec1[3], rec2[3])
	top_line = max(rec1[0], rec2[0])
	bottom_line = min(rec1[2], rec2[2])
	# judge if there is an intersect
	if left_line >= right_line or top_line >= bottom_line:
		return 0
	else:

		intersect = float(right_line - left_line) * float(bottom_line - top_line)
		#return intersect / float(sum_area - intersect)
		return intersect / float(S_rec1)

def crop_image(img,n):
    height, width, channel= img.shape[:]
    grid_h = floor(height*1.0/(n-1))
    grid_w = floor(width*1.0/(n-1))
    step_h = floor(height*float(n-2)/float(pow((n-1),2)))
    step_w = floor(width*float(n-2)/float(pow((n-1),2)))
    croped_image = np.zeros((int(grid_h),int(grid_w),pow(n,2)*channel),dtype=int)
    for i in range(n):
        for j in range(n):
            rect = [i*step_h,j*step_w,i*step_h+grid_h,j*step_w+grid_w]
            #print rect
            croped_img = img[int(rect[0]):int(rect[2]),int(rect[1]):int(rect[3]),:]
            croped_image[:,:,(i*n+j)*channel:(i*n+j+1)*channel] = croped_img[:,:,:]
    return croped_image

def filtBox(croped_rect,box):
	t_box = box[:]

	if t_box[0]<croped_rect[0]:
		t_box[0] = croped_rect[0]
	if t_box[1]<croped_rect[1]:
		t_box[1] = croped_rect[1]
	if t_box[2]>croped_rect[2]:
		t_box[2] = croped_rect[2]
	if t_box[3]>croped_rect[3]:
		t_box[3] = croped_rect[3]
	
	t_box[0] = t_box[0]-croped_rect[0]
	t_box[2] = t_box[2]-croped_rect[0]
	t_box[1] = t_box[1]-croped_rect[1]
	t_box[3] = t_box[3]-croped_rect[1]

	return t_box

def remap_boxes(temp_new_rec,n,im_size):
    #box [x1, y1, x2, y2]
    boxes = []
    box_channels = []
    gt_classes =  []
    gt_overlaps = []
    max_classes = []
    max_overlaps = []
    height = im_size[0]
    width = im_size[1]
    grid_h = floor(height*1.0/(n-1))
    grid_w = floor(width*1.0/(n-1))
    step_h = floor(height*float(n-2)/float(pow((n-1),2)))
    step_w = floor(width*float(n-2)/float(pow((n-1),2)))
    for i in range(temp_new_rec['boxes'].shape[0]):
        for j in range(n):
            for k in range(n):
                region = [step_w*k,step_h*j,step_w*k+grid_w,step_h*j+grid_h]
                box = temp_new_rec['boxes'][i].tolist()
                iou = compute_iou(box,region)
                if iou>0.8:
                    t_box = filtBox(region,box)
                    boxes.append(t_box)
                    box_channels.append(i*n+k)
                    gt_classes.append(temp_new_rec['gt_classes'][i])
                    gt_overlaps.append(temp_new_rec['gt_overlaps'][i].tolist())
                    max_classes.append(temp_new_rec['max_classes'][i])
                    max_overlaps.append(temp_new_rec['max_overlaps'][i])
                    
    temp_new_rec['boxes'] = np.asarray(boxes,dtype=np.uint16)
    temp_new_rec['box_channels'] = np.asarray(box_channels,dtype=np.uint16)
    temp_new_rec['gt_classes'] = np.asarray(gt_classes)
    temp_new_rec['gt_overlaps'] = np.asarray(gt_overlaps,dtype=np.float32)
    temp_new_rec['max_classes'] = np.asarray(max_classes)
    temp_new_rec['max_overlaps'] = np.asarray(max_overlaps)
    return

def get_crop_image(roidb, config):
    """
    preprocess image and return processed roidb
    :param roidb: a list of roidb
    :return: list of img as in mxnet format
    roidb add new item['im_info']
    0 --- x (width, second dim of im)
    |
    y (height, first dim of im)
    """
    num_images = len(roidb)
    processed_ims = []
    processed_roidb = []
    for i in range(num_images):
        roi_rec = roidb[i]
        assert os.path.exists(roi_rec['image']), '%s does not exist'.format(roi_rec['image'])
        im = cv2.imread(roi_rec['image'], cv2.IMREAD_COLOR|cv2.IMREAD_IGNORE_ORIENTATION)
        ori_shape = im.shape
        if roidb[i]['flipped']:
            im = im[:, ::-1, :]
        scale_ind = random.randrange(len(config.SCALES))
        target_size = config.SCALES[scale_ind][0]
        max_size = config.SCALES[scale_ind][1]
        croped_im = crop_image(im,config.CROP_NUM)
        im, im_scale = resize_crop(croped_im, target_size, max_size, stride=config.network.IMAGE_STRIDE)
        im_tensor = transform_crop(im, config.network.PIXEL_MEANS)
        processed_ims.append(im_tensor)
        im_info = [im_tensor.shape[2], im_tensor.shape[3], im_scale]
        remap_boxes(roi_rec,config.CROP_NUM,ori_shape)
        new_rec = roi_rec.copy()
        new_rec['boxes'] = clip_boxes(np.round(roi_rec['boxes'].copy()* im_scale), im_info[:2])
        new_rec['im_info'] = im_info
        processed_roidb.append(new_rec)
    #print "processed_ims.shape:"
    #print processed_ims[0].shape
    return processed_ims, processed_roidb

def get_segmentation_image(segdb, config):
    """
    propocess image and return segdb
    :param segdb: a list of segdb
    :return: list of img as mxnet format
    """
    num_images = len(segdb)
    assert num_images > 0, 'No images'
    processed_ims = []
    processed_segdb = []
    processed_seg_cls_gt = []
    for i in range(num_images):
        seg_rec = segdb[i]
        assert os.path.exists(seg_rec['image']), '%s does not exist'.format(seg_rec['image'])
        im = np.array(cv2.imread(seg_rec['image']))

        new_rec = seg_rec.copy()

        scale_ind = random.randrange(len(config.SCALES))
        target_size = config.SCALES[scale_ind][0]
        max_size = config.SCALES[scale_ind][1]
        im, im_scale = resize(im, target_size, max_size, stride=config.network.IMAGE_STRIDE)
        im_tensor = transform(im, config.network.PIXEL_MEANS)
        im_info = [im_tensor.shape[2], im_tensor.shape[3], im_scale]
        new_rec['im_info'] = im_info

        seg_cls_gt = np.array(Image.open(seg_rec['seg_cls_path']))
        seg_cls_gt, seg_cls_gt_scale = resize(
            seg_cls_gt, target_size, max_size, stride=config.network.IMAGE_STRIDE, interpolation=cv2.INTER_NEAREST)
        seg_cls_gt_tensor = transform_seg_gt(seg_cls_gt)

        processed_ims.append(im_tensor)
        processed_segdb.append(new_rec)
        processed_seg_cls_gt.append(seg_cls_gt_tensor)

    return processed_ims, processed_seg_cls_gt, processed_segdb

def resize_crop(im, target_size, max_size, stride=0, interpolation = cv2.INTER_LINEAR):
    """
    only resize input image to target size and return scale
    :param im: BGR image input by opencv
    :param target_size: one dimensional size (the short side)
    :param max_size: one dimensional max size (the long side)
    :param stride: if given, pad the image to designated stride
    :param interpolation: if given, using given interpolation method to resize image
    :return:
    """
    im_shape = im.shape
    im_size_min = np.min(im_shape[0:2])
    im_size_max = np.max(im_shape[0:2])
    im_scale = float(target_size) / float(im_size_min)
    # prevent bigger axis from being more than max_size:
    if np.round(im_scale * im_size_max) > max_size:
        im_scale = float(max_size) / float(im_size_max)
    channel = im.shape[2]

    t_im = cv2.resize(im[:,:,0].astype(np.float32), None, None, fx=im_scale, fy=im_scale, interpolation=interpolation)

    n_im = np.zeros((t_im.shape[0],t_im.shape[1],channel),dtype = int)

    for i in range(channel/3):
         
        n_im[:,:,i*3:(i+1)*3] = cv2.resize(im[:,:,i*3:(i+1)*3].astype(np.float32), None, None, fx=im_scale, fy=im_scale, interpolation=interpolation)

    im = n_im

    if stride == 0:
        return im, im_scale
    else:
        # pad to product of stride
        im_height = int(np.ceil(im.shape[0] / float(stride)) * stride)
        im_width = int(np.ceil(im.shape[1] / float(stride)) * stride)
        im_channel = im.shape[2]
        padded_im = np.zeros((im_height, im_width, im_channel))
        padded_im[:im.shape[0], :im.shape[1], :] = im
        del im
        return padded_im, im_scale

def transform_crop(im, pixel_means):
    """
    transform into mxnet tensor
    substract pixel size and transform to correct format
    :param im: [height, width, channel] in BGR
    :param pixel_means: [B, G, R pixel means]
    :return: [batch, channel, height, width]
    """
    channel = im.shape[2]
    im_tensor = np.zeros((1, channel, im.shape[0], im.shape[1]))
    for i in range(channel/3):
        for j in range(3):
            im_tensor[0, i*3+j, :, :] = im[:, :,i*3+ 2 - j] - pixel_means[2 - j]
    return im_tensor

def resize(im, target_size, max_size, stride=0, interpolation = cv2.INTER_LINEAR):
    """
    only resize input image to target size and return scale
    :param im: BGR image input by opencv
    :param target_size: one dimensional size (the short side)
    :param max_size: one dimensional max size (the long side)
    :param stride: if given, pad the image to designated stride
    :param interpolation: if given, using given interpolation method to resize image
    :return:
    """
    im_shape = im.shape
    im_size_min = np.min(im_shape[0:2])
    im_size_max = np.max(im_shape[0:2])
    im_scale = float(target_size) / float(im_size_min)
    # prevent bigger axis from being more than max_size:
    if np.round(im_scale * im_size_max) > max_size:
        im_scale = float(max_size) / float(im_size_max)
    im = cv2.resize(im, None, None, fx=im_scale, fy=im_scale, interpolation=interpolation)

    if stride == 0:
        return im, im_scale
    else:
        # pad to product of stride
        im_height = int(np.ceil(im.shape[0] / float(stride)) * stride)
        im_width = int(np.ceil(im.shape[1] / float(stride)) * stride)
        im_channel = im.shape[2]
        padded_im = np.zeros((im_height, im_width, im_channel))
        padded_im[:im.shape[0], :im.shape[1], :] = im
        return padded_im, im_scale

def transform(im, pixel_means):
    """
    transform into mxnet tensor
    substract pixel size and transform to correct format
    :param im: [height, width, channel] in BGR
    :param pixel_means: [B, G, R pixel means]
    :return: [batch, channel, height, width]
    """
    im_tensor = np.zeros((1, 3, im.shape[0], im.shape[1]))
    for i in range(3):
        im_tensor[0, i, :, :] = im[:, :, 2 - i] - pixel_means[2 - i]
    return im_tensor

def transform_seg_gt(gt):
    """
    transform segmentation gt image into mxnet tensor
    :param gt: [height, width, channel = 1]
    :return: [batch, channel = 1, height, width]
    """
    gt_tensor = np.zeros((1, 1, gt.shape[0], gt.shape[1]))
    gt_tensor[0, 0, :, :] = gt[:, :]

    return gt_tensor

def transform_inverse(im_tensor, pixel_means):
    """
    transform from mxnet im_tensor to ordinary RGB image
    im_tensor is limited to one image
    :param im_tensor: [batch, channel, height, width]
    :param pixel_means: [B, G, R pixel means]
    :return: im [height, width, channel(RGB)]
    """
    assert im_tensor.shape[0] == 1
    im_tensor = im_tensor.copy()
    # put channel back
    channel_swap = (0, 2, 3, 1)
    im_tensor = im_tensor.transpose(channel_swap)
    im = im_tensor[0]
    assert im.shape[2] == 3
    im += pixel_means[[2, 1, 0]]
    im = im.astype(np.uint8)
    return im

def tensor_vstack(tensor_list, pad=0):
    """
    vertically stack tensors
    :param tensor_list: list of tensor to be stacked vertically
    :param pad: label to pad with
    :return: tensor with max shape
    """
    ndim = len(tensor_list[0].shape)
    dtype = tensor_list[0].dtype
    islice = tensor_list[0].shape[0]
    dimensions = []
    first_dim = sum([tensor.shape[0] for tensor in tensor_list])
    dimensions.append(first_dim)
    for dim in range(1, ndim):
        dimensions.append(max([tensor.shape[dim] for tensor in tensor_list]))
    if pad == 0:
        all_tensor = np.zeros(tuple(dimensions), dtype=dtype)
    elif pad == 1:
        all_tensor = np.ones(tuple(dimensions), dtype=dtype)
    else:
        all_tensor = np.full(tuple(dimensions), pad, dtype=dtype)
    if ndim == 1:
        for ind, tensor in enumerate(tensor_list):
            all_tensor[ind*islice:(ind+1)*islice] = tensor
    elif ndim == 2:
        for ind, tensor in enumerate(tensor_list):
            all_tensor[ind*islice:(ind+1)*islice, :tensor.shape[1]] = tensor
    elif ndim == 3:
        for ind, tensor in enumerate(tensor_list):
            all_tensor[ind*islice:(ind+1)*islice, :tensor.shape[1], :tensor.shape[2]] = tensor
    elif ndim == 4:
        for ind, tensor in enumerate(tensor_list):
            all_tensor[ind*islice:(ind+1)*islice, :tensor.shape[1], :tensor.shape[2], :tensor.shape[3]] = tensor
    else:
        raise Exception('Sorry, unimplemented.')
    return all_tensor
