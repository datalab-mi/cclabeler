# -*- coding: utf-8 -*-
import hashlib
import json
import math
import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

from . import settings
from . import utils

datadir = os.path.join(settings.BASE_DIR, "data")
userdir = os.path.join(settings.BASE_DIR, "data", "users")
imgdir = os.path.join(settings.BASE_DIR, "data", "images")
resdir = os.path.join(settings.BASE_DIR, "data", "jsons")
markdir = os.path.join(settings.BASE_DIR, "data", "marks")

# Dictionary to reflect user connexion
users_state = {}


class Player():
    def __init__(self, name='admin', load=True):
        self.name = name
        self.password = None
        self.data, self.done, self.half = [], [], []
        jsonfile = os.path.join(userdir, name + '.json')
        if load and os.path.exists(jsonfile):
            with open(jsonfile) as f:
                userInfo = json.load(f)
                self.password = userInfo['password']
                self.data = userInfo['data']
                self.done = list(userInfo['done'])
                self.half = list(userInfo['half'])

    @property
    def pong(self):
        if self.name not in users_state:
            print('user %s is not connected!'%self.name )
            return False
        else:
            last_ping = users_state[self.name]
            print(last_ping)
            return datetime.now() - last_ping < timedelta(seconds=11)


    def disconnect(self):
        if self.name in users_state:
            users_state.pop(self.name)
            print("User %s is disconnected" % self.name)
        else:
            print('user %s is already disconnected' % self.name)
            pass

    def connect(self):
        # Update State Connexion Dictionary

        users_state.update({self.name: datetime.now()})
        print("User %s is connected" % self.name)

    def testPsd(self, psd=''):
        if self.password == None:
            return False
        if psd == self.password:
            self.connect()
            return True
        else:
            return False

    def labeling(self):
        label = "default"
        for imgid in self.data:
            if imgid not in self.done:
                label = imgid
                break
        return label

    def save(self, imgid, labels, marks, image_metadata, image_properties):
        labels = self.absLabel(imgid, labels)
        boxes, points = [], []
        for label in labels:
            if len(label) == 4:
                boxes.append(label)
            elif len(label) == 2:
                points.append(label)
        # print('utils - save - image json file:',os.path.join(resdir, imgid + '.json'))
        with open(os.path.join(resdir, imgid + '.json'), 'w+') as f:
            result = dict(
                img_id=imgid,
                metadata=image_metadata,
                properties=image_properties,
                human_num=len(labels),
                boxes=boxes,
                points=points
            )
            json.dump(result, f)
            # print('result:', result)
        with open(os.path.join(markdir, imgid + '.json'), 'w+') as f:
            json.dump(marks, f)
        # print('self.done1:', self.done)
        # print('self.half1:', self.half)
        # print('imgid:', imgid)
        marksum = sum(marks)
        if marksum <= 0:
            if len(points) > 0 or len(image_metadata) > 0:
                if imgid in self.done:
                    self.done.remove(imgid)
                if imgid not in self.half:
                    self.half += [imgid]
        elif marksum < len(marks):
            if imgid in self.done:
                self.done.remove(imgid)
            if imgid not in self.half:
                self.half += [imgid]
        else:
            if imgid in self.half:
                self.half.remove(imgid)
            if imgid not in self.done:
                self.done += [imgid]
        with open(os.path.join(userdir, self.name + '.json'), 'w+') as f:
            json.dump(dict(
                password=self.password,
                data=self.data,
                done=list(self.done),
                half=list(self.half)
            ), f)

    def getWhich(self, thisid, which):
        if which == 0:
            return self.labeling()
        ans = thisid
        if which < 0:
            for imgid in self.data:
                if thisid == imgid:
                    break
                ans = imgid
        elif which > 0:
            flag = False
            for imgid in self.data:
                if flag:
                    ans = imgid
                    break
                if thisid == imgid:
                    flag = True
        return ans

    def getLabels(self, imgid):
        jsonpath = os.path.join(resdir, imgid + '.json')
        if not os.path.exists(jsonpath):
            return []
        with open(jsonpath) as f:
            js = json.load(f)
            boxes, points = js['boxes'], js['points']

        labels = boxes + points
        return self.relLabel(imgid, labels)

    def getMarks(self, imgid, context=True):
        markpath = os.path.join(markdir, imgid + '.json')
        if not os.path.exists(markpath):
            return [0 for _ in range(256)]
        with open(markpath) as f:
            if context:
                return json.load(f)
            else:
                return f.read()

    def getMetadata(self, imgid):
        jsonpath = os.path.join(resdir, imgid + '.json')
        if not os.path.exists(jsonpath):
            return []
        with open(jsonpath) as f:
            js = json.load(f)
            if 'metadata' in js and isinstance(js['metadata'], list):
                image_metadata = js['metadata']
                # print('utils - getMetadata - image_metadata:', image_metadata)
            else:
                image_metadata = []
        return image_metadata

    def getProperties(self, imgid):
        jsonpath = os.path.join(resdir, imgid + '.json')
        if not os.path.exists(jsonpath):
            return []
        with open(jsonpath) as f:
            js = json.load(f)
            to_create = False
            if 'properties' not in js or not isinstance(js['properties'], dict) or js['properties'] == {}:
                to_create = True
            else:
                sample = {"name": "IMG_52.jpg", "extension": "jpg", "width": 1024, "height": 768, "ratio": 1.333,
                          "nb_channels": 3, "size": 129172, "md5": "28dd5483626d40175ab4cdfd69addb73"}
                for key, value in sample.items():
                    if key not in js['properties']:
                        to_create = True
            if to_create:
                image_properties = getImageProperties(os.path.join(imgdir, imgid))
                print('utils - getProperties - image_properties:', image_properties)
            else:
                image_properties = js['properties']
        return image_properties

    def absLabel(self, imgid, labels):
        img = Image.open(os.path.join(imgdir, imgid))
        w, h = img.size
        for i, label in enumerate(labels):
            for k, v in label.items():
                if 'x' in k:
                    label[k] = v * w
                elif 'y' in k:
                    label[k] = v * h
            labels[i] = label
        return labels

    def relLabel(self, imgid, labels):
        img = Image.open(os.path.join(imgdir, imgid))
        w, h = img.size
        for i, label in enumerate(labels):
            for k, v in label.items():
                if 'x' in k:
                    label[k] = v / w
                elif 'y' in k:
                    label[k] = v / h
            labels[i] = label
        return labels


def get_hash(filepath: str) -> str:
    """Returns the MD5 checksum of a file
    Args:
        filepath (str): path to file
    Returns:
        str: hash result
    """
    my_file = open(filepath, "rb")
    md5_hash = hashlib.md5()
    content = my_file.read()
    md5_hash.update(content)
    return md5_hash.hexdigest()


def getImageProperties(image_path):
    img = Image.open(image_path)
    image_name = os.path.basename(image_path)
    extension = os.path.splitext(image_path)[-1][1:].lower()
    image_width, image_height = img.size
    image_size = os.path.getsize(image_path)
    ratio = round(image_width / image_height, 3)

    nb_channels = len(img.getbands())

    with open(image_path, "rb") as f:
        md5_hash = hashlib.md5()
        content = f.read()
        md5_hash.update(content)
        md5 = md5_hash.hexdigest()

    image_properties = dict(
        name=image_name,
        extension=extension,
        width=image_width,
        height=image_height,
        ratio=ratio,
        nb_channels=nb_channels,
        size=image_size,
        md5=md5
    )
    print("image_properties:", image_properties)
    return image_properties


def init_image_jsons(imgid):
    result_json = os.path.join(resdir, imgid + '.json')
    if not os.path.exists(result_json):
        # print("result file doesnot exists :", result_json)
        with open(result_json, 'w+') as f:
            result = dict(
                img_id=imgid,
                metadata=[],
                properties=getImageProperties(os.path.join(imgdir, imgid)),
                human_num=0,
                boxes=[],
                points=[]
            )
            json.dump(result, f)
    else:
        print("result file allready exists :", result_json)
    marks_json = os.path.join(markdir, imgid + '.json')
    if not os.path.exists(marks_json):
        # print("marks file doesnot exists :", result_json)
        marks = [0 for _ in range(256)]
        with open(marks_json, 'w+') as f:
            json.dump(marks, f)
    else:
        print("marks file allready exists :", result_json)


def check_new_images():
    print('Vérification des images ...')
    userdir = utils.userdir
    imgdir = utils.imgdir
    nb_users = 0
    all_data = []
    for userjs in os.listdir(userdir):
        user_name = userjs.replace('.json', '').lower()
        if user_name not in ["admin"]:
            with open(os.path.join(userdir, userjs)) as f:
                nb_users += 1
                userdata = json.load(f)
                print('user :', userjs, 'nb_images :', len(userdata['data']), 'images :', userdata['data'])
                for img in userdata['data']:
                    all_data.append(img)
    nb_users = nb_users - 1  # Le nombre d'utilisateurs sur lesquels on va répartir les images ne contient pas 'golden'
    print('nb_users:', nb_users, 'nb_total_images:', len(all_data), 'images :', all_data)

    all_images = [image for image in os.listdir(imgdir) if os.path.splitext(image)[1] in ['.jpg', '.png', '.jpeg']]
    print('Répertoire images - nb_images :', len(all_images), 'images :', all_images)
    images_to_add = [element for element in all_images if element not in all_data]

    if len(images_to_add) == 0:
        print('Aucune nouvelle image!')
    else:
        print("{} nouvelle(s) image(s) à affecter sur {} utilisateurs".format(len(images_to_add), nb_users), ' :',
              images_to_add)
        for image_filename in images_to_add:
            print("image_filename:", image_filename)
            # On rajoute l'extension dans l'id pour gerer les differents formats
            imgid = image_filename  # Path(image_filename).stem
            init_image_jsons(imgid)

    nb_images_per_player = math.ceil(len(images_to_add) / nb_users)
    print("Nombre d'images par utilisateur :", nb_images_per_player)
    for userjs in os.listdir(userdir):
        user_name = userjs.replace('.json', '').lower()
        if user_name not in ["golden", "admin"]:
            with open(os.path.join(userdir, userjs)) as f:
                userdata = json.load(f)
                nb_images_add_to_current_player = 0
                while len(images_to_add) > 0 and nb_images_add_to_current_player < nb_images_per_player:
                    removed_image = images_to_add.pop(0)
                    userdata['data'].append(removed_image)
                    nb_images_add_to_current_player += 1
                    print('user :', userjs, 'nb:', nb_images_add_to_current_player, ' - add ', removed_image,
                          ' -img restant à affecter:', len(images_to_add))
            if nb_images_add_to_current_player > 0:
                with open(os.path.join(userdir, userjs), 'w+') as f:
                    json.dump(dict(userdata), f)
                print("Mise à jour de l'utilisateur : ", userjs, '- nb_images :', len(userdata['data']), 'images :',
                      userdata['data'])
            else:
                print("Aucune mise à jour de l'utilisateur : ", userjs)


def generate_golden_dataframe(userdir, imgdir, resdir, datadir):
    print('Génération du Golden Dataframe...')
    try:
        golden_records = []
        user_json = os.path.join(userdir, 'golden.json')
        with open(user_json) as f:
            userdata = json.load(f)
            image_names = userdata['data']
            for image_name in image_names:
                image_path = os.path.join(imgdir, image_name)
                result_path = os.path.join(resdir, image_name + '.json')
                if not os.path.exists(result_path):
                    continue
                golden_record = {'path': image_path}
                with open(result_path) as f:
                    js = json.load(f)
                    properties = js['properties']
                    golden_record.update(properties)
                    metadata = js['metadata']
                    golden_record['nb_person'] = js['human_num']
                    golden_record['result_path'] = result_path
                    golden_record['metadata'] = metadata

                    gt = []
                    for pt in js['points']:
                        x = round(pt['x'])
                        y = round(pt['y'])
                        if x < 0 or x > properties['width'] or y < 0 or y > properties['height']:
                            print("Point incohérent:")
                            print('x:', x, 'y:', y)
                            print('width:', properties['width'], 'height:', properties['height'])
                        else:
                            gt.append((x, y))
                    golden_record['ground_truth'] = gt
                    golden_records.append(golden_record)

        if len(golden_records):
            golden_dataframe = pd.DataFrame(golden_records)
            print("columns:", golden_dataframe.columns)
            golden_dataframe['path'] = golden_dataframe['path'].astype('string')
            golden_dataframe['name'] = golden_dataframe['name'].astype('string')
            golden_dataframe['extension'] = golden_dataframe['extension'].astype('category')
            golden_dataframe['width'] = golden_dataframe['width'].astype('int64')
            golden_dataframe['height'] = golden_dataframe['height'].astype('int64')
            golden_dataframe['ratio'] = golden_dataframe['ratio'].astype('float64')
            golden_dataframe['nb_channels'] = golden_dataframe['nb_channels'].astype('int64')
            golden_dataframe['size'] = golden_dataframe['size'].astype('int64')
            golden_dataframe['md5'] = golden_dataframe['md5'].astype('string')
            golden_dataframe['nb_person'] = golden_dataframe['nb_person'].astype('int64')
            golden_dataframe['result_path'] = golden_dataframe['result_path'].astype('string')

            pkl_file = os.path.join(datadir, "golden_dataframe.pkl")
            golden_dataframe.to_pickle(pkl_file)
            print("Dataframe (pkl) (", golden_dataframe.shape, ") : ", pkl_file)
            print("Dataframe dtypes :")
            print(golden_dataframe.dtypes)
            """
            Voici les dtypes attendus
            golden_dataframe.dtypes:
            path              string
            name              string
            extension       category
            width              int64
            height             int64
            ratio            float64
            nb_channels        int64
            size               int64
            md5               string
            nb_person          int64
            result_path       string
            metadata          object
            ground_truth      object
            """
            # Description statistique du contenu du dataframe
            desc_dir = os.path.join(datadir, "description")

            if not os.path.isdir(desc_dir):
                print(f'Creating {desc_dir}')
                os.makedirs(desc_dir)

            golden_dataframe_description = golden_dataframe.describe(include='all').fillna('')
            xlsx_file = os.path.join(desc_dir, "golden_dataframe_description.xlsx")
            writer = pd.ExcelWriter(xlsx_file)
            golden_dataframe_description.to_excel(writer, 'description')
            writer.save()
            print("Dataframe Description (xlsx) : ", xlsx_file)

            plot_columns = ['nb_person', 'nb_channels', 'size', 'width', 'height', 'ratio']
            for column in plot_columns:
                fig = plt.figure()
                plt.hist(golden_dataframe[column], bins=50)
                plt.ylabel('nb_images')
                plt.xlabel(column)
                plt.title("Histogram nb_images vs " + column)
                fig.savefig(os.path.join(desc_dir, "golden_dataframe_" + column + ".jpg"), dpi=fig.dpi,
                            bbox_inches='tight')
                plt.show()

            plot_columns = ['extension']
            for column in plot_columns:
                categories = golden_dataframe[column].value_counts().index
                counts = golden_dataframe[column].value_counts().values
                fig = plt.figure()
                plt.bar(categories, counts, width=0.5)
                plt.ylabel('nb_images')
                plt.xlabel(column)
                plt.title("Histogram nb_images vs " + column)
                fig.savefig(os.path.join(desc_dir, "golden_dataframe_" + column + ".jpg"), dpi=fig.dpi,
                            bbox_inches='tight')
                plt.show()

            all_metadatas = []
            for metadatas in golden_dataframe['metadata']:
                all_metadatas += metadatas

            column = 'metadata'
            df = pd.DataFrame(all_metadatas, columns=[column])
            categories = df[column].value_counts().index
            counts = df[column].value_counts().values
            fig = plt.figure()
            plt.bar(categories, counts, width=0.5)
            plt.ylabel('nb_images')
            plt.xlabel(column)
            plt.title("Histogram nb_images vs " + column)
            fig.savefig(os.path.join(desc_dir, "golden_dataframe_" + column + ".jpg"), dpi=fig.dpi, bbox_inches='tight')
            plt.show()

            print(df['metadata'].value_counts())

        else:
            print('No data found')
        return True
    except Exception as e:
        print("Exception : ", str(e))
        return False


def push_into_golden(name, imgid):
    # print("name:", name)
    # print("imgid:", imgid)
    try:
        jsonfile = os.path.join(userdir, name + '.json')
        with open(jsonfile) as f:
            userdata = json.load(f)
            data = list(userdata['data'])
            done = list(userdata['done'])
            half = list(userdata['half'])
            if imgid in data:
                data.remove(imgid)
            if imgid in done:
                done.remove(imgid)
            if imgid in half:
                half.remove(imgid)
            userdata['data'] = data
            userdata['done'] = done
            userdata['half'] = half
        with open(jsonfile, 'w+') as f:
            # print("userdata:", userdata)
            json.dump(dict(userdata), f)
        jsonfile = os.path.join(userdir, 'golden.json')
        with open(jsonfile) as f:
            userdata = json.load(f)
            data = list(userdata['data'])
            done = list(userdata['done'])
            if imgid not in data:
                data += [imgid]
            if imgid not in done:
                done += [imgid]
            userdata['data'] = data
            userdata['done'] = done
        with open(jsonfile, 'w+') as f:
            # print("userdata:", userdata)
            json.dump(dict(userdata), f)
    except Exception as e:
        print("Image transfer to golden dataset impossible : " + str(e))
        return False

    return True
