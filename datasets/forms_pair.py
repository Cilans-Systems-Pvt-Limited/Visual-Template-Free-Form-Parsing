import torch
import torch.utils.data
import numpy as np
import json
from skimage import io
from skimage import draw
#import skimage.transform as sktransform
import os
import math
import cv2

IAIN_CATCH=['193','194','197','200']

def fixAssumptions(annotations):
    #print('TODO')
    toAdd=[]
    toAddSame=[]

    for pair in annotations['samePairs']:
        notNum=num=None
        if annotations['byId'][pair[0]]['type']=='textNumber':
            num=annotations['byId'][pair[0]]
            notNum=annotations['byId'][pair[1]]
        elif annotations['byId'][pair[1]]['type']=='textNumber':
            num=annotations['byId'][pair[1]]
            notNum=annotations['byId'][pair[0]]

        if notNum is not None and notNum['type']!='textNumber':
            for pair2 in annotations['pairs']:
                if notNum['id'] in pair2:
                    if notNum['id'] == pair2[0]:
                        otherId=pair2[1]
                    else:
                        otherId=pair2[0]
                    if annotations[otherId]['type']=='fieldCol' or annotations[otherId]['type']=='fieldRow':
                        toAdd.append([num['id'],otherId])

    #heirarchy labels.
    #for pair in annotations['samePairs']:
    #    text=textMinor=None
    #    if annotations['byId'][pair[0]]['type']=='text':
    #        text=pair[0]
    #        if annotations['byId'][pair[1]]['type']=='textMinor':
    #            textMinor=pair[1]
    #    elif annotations['byId'][pair[1]]['type']=='text':
    #        text=pair[1]
    #        if annotations['byId'][pair[0]]['type']=='textMinor':
    #            textMinor=pair[0]
    #    else:#catch case of minor-minor-field
    #        if annotations['byId'][pair[1]]['type']=='textMinor' and annotations['byId'][pair[0]]['type']=='textMinor':
    #            a=pair[0]
    #            b=pair[1]
    #            for pair2 in annotations['pairs']:
    #                if a in pair2:
    #                    if pair2[0]==a:
    #                        otherId=pair2[1]
    #                    else:
    #                        otherId=pair2[0]
    #                    toAdd.append([b,otherId])
    #                if b in pair2:
    #                    if pair2[0]==b:
    #                        otherId=pair2[1]
    #                    else:
    #                        otherId=pair2[0]
    #                    toAdd.append([a,otherId])

    #    
    #    if text is not None and textMinor is not None:
    #        for pair2 in annotations['pairs']:
    #            if textMinor in pair2:
    #                if pair2[0]==textMinor:
    #                    otherId=pair2[1]
    #                else:
    #                    otherId=pair2[0]
    #                toAdd.append([text,otherId])
    #        for pair2 in annotations['samePairs']:
    #            if textMinor in pair2:
    #                if pair2[0]==textMinor:
    #                    otherId=pair2[1]
    #                else:
    #                    otherId=pair2[0]
    #                if annotations['byId'][otherId]['type']=='textMinor':
    #                    toAddSame.append([text,otherId])

    annotations['samePairs']+=toAddSame
    annotations['pairs']+=toAdd


class FormsPair(torch.utils.data.Dataset):
    """
    Class for reading AI2D dataset and creating query/result masks from bounding polygons
    """

    def __getResponseBBList(self,queryId,annotations):
        responseBBList=[]
        for pair in annotations['pairs']+annotations['samePairs']:
            if queryId in pair:
                if pair[0]==queryId:
                    otherId=pair[1]
                else:
                    otherId=pair[0]
                poly = np.array(annotations['byId'][otherId]['poly_points']) #self.__getResponseBB(otherId,annotations)  
                responseBBList.append(poly)
        return responseBBList


    def __init__(self, dirPath=None, split=None, config=None, instances=None, test=False):
        self.cache_resized=False
        if 'augmentation_params' in config:
            self.augmentation_params=config['augmentation_params']
        else:
            self.augmentation_params=None
        if 'no_blanks' in config:
            self.no_blanks = config['no_blanks']
        else:
            self.no_blanks = False
        if 'no_print_fields' in config:
            self.no_print_fields = config['no_print_fields']
        else:
            self.no_print_fields = False
        patchSize=config['patch_size']
        if instances is not None:
            self.instances=instances
            self.cropResize = self.__cropResizeF(patchSize,0,0)
        else:
            centerJitterFactor=config['center_jitter']
            sizeJitterFactor=config['size_jitter']
            self.cropResize = self.__cropResizeF(patchSize,centerJitterFactor,sizeJitterFactor)
            with open(os.path.join(dirPath,'train_valid_test_split.json')) as f:
                groupsToUse = json.loads(f.read())[split]
            self.instances=[]
            if test:
                aH=0
                aW=0
                aA=0
            for groupName, imageNames in groupsToUse.items():
                if groupName in IAIN_CATCH:
                    print('Skipped group {} as Iain has incomplete GT here'.format(groupName))
                    continue
                for imageName in imageNames:
                    org_path = os.path.join(dirPath,'groups',groupName,imageName)
                    #print(org_path)
                    if self.cache_resized:
                        path = os.path.join(self.cache_path,imageName)
                    else:
                        path = org_path
                    jsonPath = org_path[:org_path.rfind('.')]+'.json'
                    annotations=None
                    if os.path.exists(jsonPath):
                        rescale=1.0
                        if self.cache_resized and not os.path.exists(path):
                            org_img = cv2.imread(org_path)
                            target_dim1 = self.rescale_range[1]
                            target_dim0 = int(org_img.shape[0]/float(org_img.shape[1]) * target_dim1)
                            resized = cv2.resize(org_img,(target_dim1, target_dim0), interpolation = cv2.INTER_CUBIC)
                            cv2.imwrite(path,resized)
                            rescale = target_dim1/float(org_img.shape[1])
                        elif self.cache_resized:
                            with open(os.path.join(jsonPath)) as f:
                                annotations = json.loads(f.read())
                            imW = annotations['width']
                                    
                            target_dim1 = self.rescale_range[1]
                            rescale = target_dim1/float(imW)
                        if annotations is None:
                            with open(os.path.join(jsonPath)) as f:
                                annotations = json.loads(f.read())
                            #print(os.path.join(jsonPath))
                        imH = annotations['height']
                        imW = annotations['width']
                        #startCount=len(self.instances)
                        if test:
                            aH+=imH
                            aW+=imW
                            aA+=imH*imW
                        annotations['byId']={}
                        for bb in annotations['textBBs']:
                            annotations['byId'][bb['id']]=bb
                        for bb in annotations['fieldBBs']:
                            annotations['byId'][bb['id']]=bb

                        #fix assumptions made in GTing
                        #fixAssumptions(annotations)

                        #print(path)
                        for bb in annotations['textBBs']:
                            bbPoints = np.array(bb['poly_points'])
                            responseBBList = self.__getResponseBBList(bb['id'],annotations)
                            #print(bb['id'])
                            #print(responseBBList)
                            self.instances.append({
                                                'id': bb['id'],
                                                'imagePath': path,
                                                'queryPoly': bbPoints,
                                                'responsePolyList': responseBBList,
                                                'helperStats': self.__getHelperStats(bbPoints, responseBBList, imH, imW)
                                            })

                        for bb in annotations['fieldBBs']:
                            if ( (self.no_blanks and (bb['isBlank']=='blank' or bb['isBlank']==3)) or
                                 (self.no_print_fields and (bb['isBlank']=='print' or bb['isBlank']==2)) ):
                                 continue
                            bbPoints = np.array(bb['poly_points'])
                            responseBBList = self.__getResponseBBList(bb['id'],annotations)
                            self.instances.append({
                                                'id': bb['id'],
                                                'imagePath': path,
                                                'queryPoly': bbPoints,
                                                'responsePolyList': responseBBList,
                                                'helperStats': self.__getHelperStats(bbPoints, responseBBList, imH, imW)
                                            })

                        #for i in range(startCount,len(self.instances)):
                            #    try:
                                #        #self.helperStats.append((0,0,0,0,0,0,0))
                        #    except ValueError as err:
                                #        print('error on image '+image+', id '+self.ids[i])
                        #        print(os.path.join(dirPath,'annotationsMod',image+'.json'))
                        #        print(err)
                        #        exit(2)
                if test:
                    with open(os.path.join(dirPath,'annotationsMod',image+'.json')) as f:
                        annotations = json.loads(f.read())
                        imH = annotations['height']
                        imW = annotations['width']
                        aH+=imH
                        aW+=imW
                        aA+=imH*imW
        
        if test:
            print('average height: '+str(aH/len(imageToCategories)))
            print('average width:  '+str(aW/len(imageToCategories)))
            print('average area:   '+str(aA/len(imageToCategories)))



    def __len__(self):
        return len(self.instances)

    def __getitem__(self,index):
        id = self.instances[index]['id']
        imagePath = self.instances[index]['imagePath']
        queryPoly = self.instances[index]['queryPoly']
        responsePolyList = self.instances[index]['responsePolyList']
        xQueryC,yQueryC,reach,x0,y0,x1,y1 = self.instances[index]['helperStats']
        #print(index)
        #print(self.imagePath)
        #print(self.ids[index])
        image = 1.0 - cv2.imread(imagePath)/128.0
        #TODO color jitter, rotation?, skew?
        queryMask = np.zeros([image.shape[0],image.shape[1]])
        rr, cc = draw.polygon(queryPoly[:, 1], queryPoly[:, 0], queryMask.shape)
        queryMask[rr,cc]=1
        responseMask = np.zeros([image.shape[0],image.shape[1]])
        for poly in responsePolyList:
            rr, cc = draw.polygon(poly[:, 1], poly[:, 0], responseMask.shape)
            responseMask[rr,cc]=1

        imageWithQuery = np.append(image,queryMask.reshape(queryMask.shape+(1,)),axis=2)
        imageWithQuery = np.moveaxis(imageWithQuery,2,0)
        sample = self.cropResize(imageWithQuery, responseMask, xQueryC,yQueryC,reach,x0,y0,x1,y1)
        #sample = (imageWithQuery, responseMask,) + helperStats + (imagePath+' '+id,)
        if self.augmentation_params is not None:
            sample = self.augment(sample)
        return sample #+ (imagePath+' '+id,)

    def __getHelperStats(self, queryPoly, polyList, imH, imW):
        """
        This returns stats used when putting a batch together, croping and resizeing windows.
        It returns
            the centerpoint of the query mask,
            the furthest response mask point from the center (minimum set by query mask size in case no response)
            the bounding rectangle containing all masks
        """
        x0 = minXQuery = np.amin(queryPoly[:,0])
        x1 = maxXQuery = np.amax(queryPoly[:,0])
        y0 = minYQuery = np.amin(queryPoly[:,1])
        y1 = maxYQuery = np.amax(queryPoly[:,1])
        queryCenterX = (maxXQuery+minXQuery)/2
        queryCenterY = (maxYQuery+minYQuery)/2

        if x1>=imW or y1>=imH:
            raise ValueError('query point outside image ('+str(imH)+', '+str(imW)+'): y='+str(y1)+' x='+str(x1)+'   '+str(queryPoly))

        def dist(x,y):
            return math.sqrt((queryCenterX-x)**2 + (queryCenterY-y)**2)

        maxDistFromCenter = maxXQuery-minXQuery+maxYQuery-minYQuery
        for poly in polyList:
            minX = np.amin(poly[:,0])
            maxX = np.amax(poly[:,0])
            minY = np.amin(poly[:,1])
            maxY = np.amax(poly[:,1])
            if maxX>=imW or maxY>=imH:
                raise ValueError('resp point outside image ('+str(imH)+', '+str(imW)+'): y='+str(maxY)+' x='+str(maxX))
            maxDistFromCenter = max(maxDistFromCenter, dist(minX,minY), dist(minX,maxY), dist(maxX,minY), dist(maxX,maxY))
            x0 = min(x0,minX)
            x1 = max(x1,maxX)
            y0 = min(y0,minY)
            y1 = max(y1,maxY)
        ###
        #if (imH==183 and imW==183):
        #    print(( queryCenterX, queryCenterY, maxDistFromCenter, int(x0),int(y0),int(x1),int(y1)))
        return ( queryCenterX, queryCenterY, maxDistFromCenter, int(x0),int(y0),int(x1),int(y1))

    def __cropResizeF(self,patchSize, centerJitterFactor, sizeJitterFactor):
        """
        Returns function which crops and pads data to include all masks (mostly) and be uniform size
        """

        #resizeImage=transforms.Resize((patchSize, patchSize))
        def squareBB(x0,x1,dimLen,toFill):
            run = x0 + dimLen-x1
            if run<=toFill:
                new_x0=0
                new_x1=dimLen
            else:
                play = run-toFill
                new_x0 = max(np.random.randint(x0-toFill,x0),0)
                toFill -= x0-new_x0
                new_x1 = min(x1+toFill,dimLen)
                toFill -= new_x1-x1
                new_x0 = new_x0-toFill
                assert(new_x0>=0)
            return new_x0, new_x1

        def cropResize(image,label,xQueryC,yQueryC,reach,x0,y0,x1,y1):
            xc = int(min(max( xQueryC + np.random.normal(0,reach*centerJitterFactor) ,0),image.shape[2]-1))
            yc = int(min(max( yQueryC + np.random.normal(0,reach*centerJitterFactor) ,0),image.shape[1]-1))
            radius = int(reach + np.random.normal(reach*centerJitterFactor,reach*sizeJitterFactor))

            if radius<=0:
                radius=int(reach//2)
            #make radius smaller if we go off image, randomly
            #then make radius big enough to include all masks, randomly
            if centerJitterFactor==0:
                #not random if valid
                if xc+radius>image.shape[2]-1:
                    radius = image.shape[2]-1-xc
                if xc-radius<0:
                    radius = xc
                if yc+radius+1>image.shape[1]:
                    radius = image.shape[1]-yc-1
                if yc-radius<0:
                    radius = yc

                if xc+radius<x1:
                    radius= x1-xc
                if xc-radius>x0:
                    radius = xc-x0
                if yc+radius<y1:
                    radius = y1-yc
                if yc-radius>y0:
                    radius = yc-y0
            else:
                if xc+radius>image.shape[2]-1:
                    radius = np.random.randint(image.shape[2]-1-xc, radius+1)
                if xc-radius<0:
                    radius = np.random.randint(xc, radius+1)
                if yc+radius+1>image.shape[1]:
                    radius = np.random.randint(image.shape[1]-yc-1, radius+1)
                if yc-radius<0:
                    radius = np.random.randint(yc, radius+1)


                if xc+radius<x1:
                    radius= np.random.randint(radius,x1-xc +1)
                if xc-radius>x0:
                    radius = np.random.randint(radius, xc-x0 +1)
                if yc+radius<y1:
                    radius = np.random.randint(radius, y1-yc +1)
                if yc-radius>y0:
                    radius = np.random.randint(radius, yc-y0 +1)

            
            #are to going to expand the image? Don't
            if radius < patchSize/2.0:
                radius = patchSize/2.0 + abs(np.random.normal(0,reach*sizeJitterFactor/2))

            cropOutX0 = int(max(xc-radius,0))
            cropOutY0 = int(max(yc-radius,0))
            cropOutX1 = int(min(xc+radius+1,image.shape[2]))
            cropOutY1 = int(min(yc+radius+1,image.shape[1]))

            size = (cropOutY1-cropOutY0,cropOutX1-cropOutX0)
            if size[0]!=size[1]:
                #force square, if possible
                if size[0] < size[1]:
                    cropOutY0, cropOutY1 = squareBB(cropOutY0, cropOutY1, image.shape[1], size[1]-size[0])
                else:
                    cropOutX0, cropOutX1 = squareBB(cropOutX0, cropOutX1, image.shape[2], size[0]-size[1])
                size = (cropOutY1-cropOutY0,cropOutX1-cropOutX0)
            bbSize = radius*2+1
            if size[0]!=bbSize and size[1]!=bbSize:
                bbSize = max(size[0],size[1])

            #print(id)
            #print('image shape: '+str(image.shape))
            #print((xQueryC,yQueryC,reach,x0,y0,x1,y1))
            #print((xc,yc,(bbSize-1)/2))
            #print((cropOutX0, cropOutY0, cropOutX1, cropOutY1))
            #print(size)
            
            assert(size[0]<=bbSize and size[1]<=bbSize)
            if size[0]!=size[1]:

                diffH = (bbSize)-size[0]
                if diffH==0 or centerJitterFactor==0:
                    padTop=0
                else:
                    padTop = np.random.randint(0,diffH)

                diffW = (bbSize)-size[1]
                if diffW==0 or centerJitterFactor==0:
                    padLeft=0
                else:
                    padLeft = np.random.randint(0,diffW)

                imagePatch = np.zeros((image.shape[0],bbSize,bbSize), dtype=np.float32)
                imagePatch[:,padTop:size[0]+padTop,padLeft:size[1]+padLeft] = image[:,cropOutY0:cropOutY1,cropOutX0:cropOutX1]
                labelPatch = np.zeros((bbSize,bbSize), dtype=np.float32)
                labelPatch[padTop:size[0]+padTop,padLeft:size[1]+padLeft] = label[cropOutY0:cropOutY1,cropOutX0:cropOutX1]
            else:
                imagePatch = image[:,cropOutY0:cropOutY1,cropOutX0:cropOutX1]
                labelPatch = label[cropOutY0:cropOutY1,cropOutX0:cropOutX1]

            #retImage = sktransform.resize(imagePatch.transpose((1, 2, 0)),(patchSize,patchSize)).transpose((2, 0, 1))
            #retLabel = sktransform.resize(labelPatch, (patchSize,patchSize))
            retImage = cv2.resize(imagePatch.transpose((1, 2, 0)),(patchSize,patchSize)).transpose((2, 0, 1))
            retLabel = cv2.resize(labelPatch, (patchSize,patchSize))
            retImage = torch.from_numpy(retImage.astype(np.float32))
            retLabel = torch.from_numpy(retLabel.astype(np.float32))
            return (retImage, retLabel)

        return cropResize