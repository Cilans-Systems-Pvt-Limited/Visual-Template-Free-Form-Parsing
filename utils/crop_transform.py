import numpy as np
import cv2
import timeit

def perform_crop(img, gt, crop):
    cs = crop['crop_size']
    cropped_gt_img = img[crop['dim0'][0]:crop['dim0'][1], crop['dim1'][0]:crop['dim1'][1]]
    scaled_gt_img = cv2.resize(cropped_gt_img, (cs, cs), interpolation = cv2.INTER_CUBIC)
    scaled_gt = None
    if gt is not None:
        cropped_gt = gt[crop['dim0'][0]:crop['dim0'][1], crop['dim1'][0]:crop['dim1'][1]]
        scaled_gt = cv2.resize(cropped_gt, (cs, cs), interpolation = cv2.INTER_CUBIC)
        if len(scaled_gt.shape)==2:
            scaled_gt = scaled_gt[...,None]
    return scaled_gt_img, scaled_gt


def generate_random_crop(img, pixel_gt, line_gts, point_gts, params):
    
    contains_label = np.random.random() < params['prob_label'] if 'prob_label' in params else None
    cs = params['crop_size']

    cnt = 0
    while True:

        dim0 = np.random.randint(0,img.shape[0]-cs)
        dim1 = np.random.randint(0,img.shape[1]-cs)

        crop = {
            "dim0": [dim0, dim0+cs],
            "dim1": [dim1, dim1+cs],
            "crop_size": cs
        }

        line_gt_match={}
        hit=False
        for name, gt in line_gts.items():
            ##tic=timeit.default_timer()
            line_gt_match[name] = np.zeros_like(gt)
            line_gt_match[name][...,0][gt[...,0] < dim1] = 1
            line_gt_match[name][...,0][gt[...,0] > dim1+cs] = 1

            line_gt_match[name][...,1][gt[...,1] < dim0] = 1
            line_gt_match[name][...,1][gt[...,1] > dim0+cs] = 1

            line_gt_match[name][...,0][gt[...,2] < dim1] = 1
            line_gt_match[name][...,0][gt[...,2] > dim1+cs] = 1

            line_gt_match[name][...,1][gt[...,3] < dim0] = 1
            line_gt_match[name][...,1][gt[...,3] > dim0+cs] = 1

            line_gt_match[name] = 1-line_gt_match[name]
            line_gt_match[name] = np.logical_and.reduce((line_gt_match[name][...,0], line_gt_match[name][...,1], line_gt_match[name][...,2], line_gt_match[name][...,3]))
            if line_gt_match[name].sum() > 0:
                hit=True
        point_gt_match={}
        for name, gt in point_gts.items():
            ##tic=timeit.default_timer()
            point_gt_match[name] = np.zeros_like(gt)
            point_gt_match[name][...,0][gt[...,0] < dim1] = 1
            point_gt_match[name][...,0][gt[...,0] > dim1+cs] = 1

            point_gt_match[name][...,1][gt[...,1] < dim0] = 1
            point_gt_match[name][...,1][gt[...,1] > dim0+cs] = 1

            point_gt_match[name] = 1-point_gt_match[name]
            point_gt_match[name] = np.logical_and(point_gt_match[name][...,0], point_gt_match[name][...,1])
            if point_gt_match[name].sum() > 0:
                hit=True
            ##print('match: {}'.format(timeit.default_timer()-##tic))
        
        if contains_label is not None:
            if hit and contains_label or cnt > 100:
                cropped_gt_img, cropped_pixel_gt = perform_crop(img,pixel_gt, crop)
                for name in line_gts:
                    line_gt_match[name] = np.where(line_gt_match[name]!=0)
                for name in point_gts:
                    point_gt_match[name] = np.where(point_gt_match[name]!=0)
                return crop, cropped_gt_img, cropped_pixel_gt, line_gt_match, point_gt_match

            if not hit and not contains_label:
                cropped_gt_img, cropped_pixel_gt = perform_crop(img,pixel_gt, crop)
                for name in line_gts:
                    line_gt_match[name] = np.where(line_gt_match[name]!=0)
                for name in point_gts:
                    point_gt_match[name] = np.where(point_gt_match[name]!=0)
                return crop, cropped_gt_img, cropped_pixel_gt, line_gt_match, point_gt_match

        else:
            ##tic=timeit.default_timer()
            cropped_gt_img, cropped_pixel_gt = perform_crop(img,pixel_gt, crop)
            ##print('perform_crop: {}'.format(timeit.default_timer()-##tic))
            ##tic=timeit.default_timer()
            for name in line_gts:
                line_gt_match[name] = np.where(line_gt_match[name]!=0)
            for name in point_gts:
                point_gt_match[name] = np.where(point_gt_match[name]!=0)
            ##print('where: {}'.format(timeit.default_timer()-##tic))
            return crop, cropped_gt_img, cropped_pixel_gt, line_gt_match, point_gt_match

        cnt += 1

class CropTransform(object):
    def __init__(self, crop_params):
        crop_size = crop_params['crop_size']
        self.random_crop_params = crop_params
        if 'pad' in crop_params:
            pad_by = crop_params['pad']
        else:
            pad_by = crop_size//2
        self.pad_params = ((pad_by,pad_by),(pad_by,pad_by),(0,0))

    def __call__(self, sample):
        org_img = sample['img']
        line_gts = sample['line_gt']
        point_gts = sample['point_gt']
        pixel_gt = sample['pixel_gt']

        #pad out to allow random samples to take space off of the page
        ##tic=timeit.default_timer()
        #org_img = np.pad(org_img, self.pad_params, 'mean')
        org_img = np.pad(org_img, self.pad_params, 'constant')
        if pixel_gt is not None:
            pixel_gt = np.pad(pixel_gt, self.pad_params, 'constant')
        ##print('pad: {}'.format(timeit.default_timer()-##tic))
        
        ##tic=timeit.default_timer()
        j=0
        #pad the points accordingly
        for name, gt in line_gts.items():
            gt[:,:,0] = gt[:,:,0] + self.pad_params[0][0]
            gt[:,:,1] = gt[:,:,1] + self.pad_params[1][0]

            gt[:,:,2] = gt[:,:,2] + self.pad_params[0][0]
            gt[:,:,3] = gt[:,:,3] + self.pad_params[1][0]
        for name, gt in point_gts.items():
            gt[:,:,0] = gt[:,:,0] + self.pad_params[0][0]
            gt[:,:,1] = gt[:,:,1] + self.pad_params[1][0]

        crop_params, org_img, pixel_gt, line_gt_match, point_gt_match = generate_random_crop(org_img, pixel_gt, line_gts, point_gts, self.random_crop_params)
        #print(crop_params)
        #print(gt_match)
        
        ##tic=timeit.default_timer()
        new_line_gts={}
        for name, gt in line_gts.items():
            gt = gt[line_gt_match[name]][None,...] #add batch dim (?)
            gt[...,0] = gt[...,0] - crop_params['dim1'][0]
            gt[...,1] = gt[...,1] - crop_params['dim0'][0]

            gt[...,2] = gt[...,2] - crop_params['dim1'][0]
            gt[...,3] = gt[...,3] - crop_params['dim0'][0]
            new_line_gts[name]=gt
        new_point_gts={}
        for name, gt in point_gts.items():
            gt = gt[point_gt_match[name]][None,...] #add batch dim (?)
            gt[...,0] = gt[...,0] - crop_params['dim1'][0]
            gt[...,1] = gt[...,1] - crop_params['dim0'][0]
            new_point_gts[name]=gt
        ##print('pad-minus: {}'.format(timeit.default_timer()-##tic))

            #if 'start' in name:
            #    for j in range(min(10,gt.size(1))):
            #        ##print('a {},{}   {},{}'.format(gt[:,j,0],gt[:,j,1],gt[:,j,2],gt[:,j,3]))

        return {
            "img": org_img,
            "line_gt": new_line_gts,
            "point_gt": new_point_gts,
            "pixel_gt": pixel_gt
        }
