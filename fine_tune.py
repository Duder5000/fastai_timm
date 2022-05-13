import wandb
import timm
import argparse
import torchvision
from fastai.vision.all import *
from fastai.callback.wandb import WandbCallback

WANDB_PROJECT = 'fine_tune_timm'

config_defaults = SimpleNamespace(
    batch_size=64,
    epochs=5,
    num_experiments=3,
    learning_rate=2e-3,
    img_size=224,
    resize_method="crop",
    model_name="resnet34",
    concat_pool=False,
    seed=42,
    force_torchvision=False,
    wandb_project=WANDB_PROJECT,
    split_func="default",
)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch_size', type=int, default=config_defaults.batch_size)
    parser.add_argument('--epochs', type=int, default=config_defaults.epochs)
    parser.add_argument('--num_experiments', type=int, default=config_defaults.num_experiments)
    parser.add_argument('--learning_rate', type=float, default=config_defaults.learning_rate)
    parser.add_argument('--img_size', type=int, default=config_defaults.img_size)
    parser.add_argument('--resize_method', type=str, default=config_defaults.resize_method)
    parser.add_argument('--model_name', type=str, default=config_defaults.model_name)
    parser.add_argument('--split_func', type=str, default=config_defaults.split_func)
    parser.add_argument('--concat_pool', action='store_true')
    parser.add_argument('--seed', type=int, default=config_defaults.seed)
    parser.add_argument('--force_torchvision', action='store_true')
    parser.add_argument('--wandb_project', type=str, default=WANDB_PROJECT)
    return parser.parse_args()

def get_gpu_mem(device=0):
    "Memory usage in GB"
    gpu_mem = torch.cuda.memory_stats_as_nested_dict(device=device)
    return (gpu_mem["reserved_bytes"]["small_pool"]["peak"] + gpu_mem["reserved_bytes"]["large_pool"]["peak"])*1024**-3
                                     
def get_pets(batch_size, img_size, seed, method="crop"):
    dataset_path = untar_data(URLs.PETS)
    files = get_image_files(dataset_path/"images")
    dls = ImageDataLoaders.from_name_re(dataset_path, files, 
                                        r'(^[a-zA-Z]+_*[a-zA-Z]+)', 
                                        valid_pct=0.2, 
                                        seed=seed, 
                                        bs=batch_size,
                                        item_tfms=Resize(img_size, method=method)) 
    return dls
    

top_5_accuracy = partial(top_k_accuracy, k=5)
    
def train(config=config_defaults):
    print(f"\n >> Training {config.model_name}\n")
    for _ in range(config.num_experiments):
        with wandb.init(project=config.wandb_project, group="torchvision" if config.force_torchvision else "timm", config=config):
            config = wandb.config
            dls = get_pets(config.batch_size, config.img_size, config.seed, config.resize_method)
            if config.force_torchvision: 
                config.model_name = getattr(torchvision.models, config.model_name)
            learn = vision_learner(dls, 
                                   config.model_name, 
                                   metrics=[accuracy, error_rate, top_5_accuracy], 
                                   concat_pool=config.concat_pool,
                                   splitter=default_split if config.split_func=="default" else None,
                                   cbs=WandbCallback(log_preds=False)).to_fp16()
            learn.fine_tune(config.epochs, config.learning_rate)
            wandb.summary({"GPU_mem": get_gpu_mem(learn.dls.device)})
    
if __name__ == "__main__":
    args = parse_args()
    train(config=args)
    
    



