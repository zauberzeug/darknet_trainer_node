from learning_loop_node.trainer.downloader import DataDownloader as Downloader
from learning_loop_node.trainer.downloader_factory import DownloaderFactory
from learning_loop_node.context import Context
from learning_loop_node.trainer.trainer import Trainer
from darknet_trainer import DarknetTrainer
from glob import glob
import os
import learning_loop_node.trainer.tests.trainer_test_helper as trainer_test_helper
from learning_loop_node import node_helper

from learning_loop_node.globals import GLOBALS


def get_files_from_data_folder():
    files = [entry for entry in glob(f'{GLOBALS.data_folder}/**/*', recursive=True)
             if os.path.isfile(entry) or os.path.islink(entry)]
    files.sort()
    return files


def create_darknet_trainer() -> DarknetTrainer:
    return DarknetTrainer(model_format='yolo')


def create_downloader() -> Downloader:
    context = Context(organization='zauberzeug', project='pytest')
    return DownloaderFactory.create(context=context)


async def downlaod_data(trainer: Trainer):
    model_id = await trainer_test_helper.assert_upload_model(
        ['tests/integration/data/' + f for f in ['model.weights', 'training.cfg', 'names.txt']],
        format='yolo'
    )
    context = Context(organization='zauberzeug', project='pytest')
    training = Trainer.generate_training(context, {'id': model_id})
    downloader = create_downloader()
    training.data = await downloader.download_data(training.images_folder)
    await node_helper.download_model(training.training_folder, context, model_id, 'yolo')

    trainer.training = training
