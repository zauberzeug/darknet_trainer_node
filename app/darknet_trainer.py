import shutil
from learning_loop_node.trainer.model import BasicModel, Model
import traceback
from typing import List, Optional, Union
from learning_loop_node.trainer.trainer import Trainer
import yolo_helper
import helper
import yolo_cfg_helper
import subprocess
import os
import psutil
import model_updater
import logging

logging.basicConfig(level=logging.DEBUG)

class DarknetTrainer(Trainer):
    latest_published_iteration: Union[int, None]

    async def start_training(self) -> None:
        await self.prepare_training()
        training_path = self.training.training_folder
        weightfile = yolo_helper.find_weightfile(training_path)
        cfg_file = yolo_cfg_helper._find_cfg_file(training_path)

        # NOTE we have to write the pid inside the bash command to get the correct pid.
        cmd = f'cd {training_path};nohup /darknet/darknet detector train data.txt {cfg_file} {weightfile} -dont_show -map -clear >> last_training.log 2>&1 & echo $! > last_training.pid'
        p = subprocess.Popen(cmd, shell=True)
        _, err = p.communicate()
        if p.returncode != 0:
            raise Exception(f'Failed to start training with error: {err}')

    async def prepare_training(self) -> None:
        training_folder = self.training.training_folder
        image_folder = self.training.images_folder
        training_data = self.training.data

        yolo_helper.create_backup_dir(training_folder)

        image_folder_for_training = yolo_helper.create_image_links(
            training_folder, image_folder, training_data.image_ids())
        await yolo_helper.update_yolo_boxes(image_folder_for_training, training_data)
        box_category_names = helper.get_box_category_names(training_data)
        yolo_helper.create_names_file(training_folder, box_category_names)
        yolo_helper.create_data_file(training_folder, len(box_category_names))
        yolo_helper.create_train_and_test_file(
            training_folder, image_folder_for_training, training_data.image_data)
        yolo_cfg_helper.replace_classes_and_filters(len(box_category_names), training_folder)
        yolo_cfg_helper.update_anchors(training_folder)

    def is_training_alive(self) -> bool:
        try:
            training_folder = self.training.training_folder
            pid_path = f'{training_folder}/last_training.pid'
            if not os.path.exists(pid_path):
                return False
            with open(pid_path, 'r') as f:
                pid = f.read().strip()
            try:
                p = psutil.Process(int(pid))
            except psutil.NoSuchProcess as e:
                return False
            if p.name() != 'darknet':
                return False

            with open(f'{training_folder}/last_training.log') as f:
                if 'CUDA Error: out of memory' in f.readlines():
                    logging.error('graphics card is out of memory')
                    return False
            return True
        except:
            traceback.print_exc()
        return False

    def get_model_files(self, model_id) -> List[str]:
        from glob import glob
        try:
            weightfile_path = glob(f'/data/**/trainings/**/{model_id}.weights', recursive=True)[0]
        except:
            raise Exception(f'No model found for id: {model_id}.')

        training_path = '/'.join(weightfile_path.split('/')[:-1])
        cfg_file_path = yolo_cfg_helper._find_cfg_file(training_path)
        return [weightfile_path, f'{cfg_file_path}', f'{training_path}/names.txt']

    def get_new_model(self) -> Optional[BasicModel]:
        return model_updater.check_state(self.training.id, self.training.data, self.latest_published_iteration)

    def on_model_published(self, basic_model: BasicModel, uuid: str) -> None:
        self.latest_published_iteration = basic_model.meta_information['iteration']
        weightfile_path = basic_model.meta_information['weightfile_path']
        path = weightfile_path.rsplit('/', 2)[0]
        new_filename = path + f'/{uuid}.weights'
        shutil.move(weightfile_path, new_filename)

    def stop_training(self) -> None:
        cmd = f'cd {self.training.training_folder};kill -9 `cat last_training.pid` || echo "no such file"; rm -f last_training.pid'
        p = subprocess.Popen(cmd, shell=True)
        std, err = p.communicate()
        if p.returncode != 0:
            raise Exception(f'Failed to stop training with error: {std}, {err}')

    def _show_log(self) -> str:
        if not self.training:
            raise Exception('no training running')
        with open(f'{self.training.training_folder}/last_training.log', 'r') as f:
            return f.read()