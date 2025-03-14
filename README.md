This repo is a fork of MIMO-Unet; I (Becky) am adding on some additional loss functions to work with covariances between pixels.

<a target="_blank" href="https://colab.research.google.com/github/antonbaumann/MIMO-Unet/blob/main/MIMO_U_Net_NYUv2_depth.ipynb">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

# Probabilistic MIMO U-Net

This repository contains the code for the paper [Probabilistic MIMO U-Net: Efficient and Accurate Uncertainty Estimation for Pixel-wise Regression](https://arxiv.org/abs/2308.07477).

Authors: [Anton Baumann](https://scholar.google.com/citations?user=4CEGXaYAAAAJ)<sup>1</sup>, [Thomas Roßberg](https://www.unibw.de/lrt9/lrt-9.3/personen/dipl-ing-thomas-rossberg)<sup>1</sup>, [Michael Schmitt](https://scholar.google.de/citations?user=CVnD4h4AAAAJ)<sup>1</sup>\
<sup>1</sup> University of the Bundeswehr Munich\
in UnCV Workshop at ICCV 2023 (Oral Presentation)

![MIMO U-Net](MIMO_Unet_Highlevel_colors.jpg "MIMO U-Net")

## Installation
```bash
git clone https://github.com/antonbaumann/MIMO-Unet.git
cd MIMO-Unet
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:MIMO_REPOSITORY_PATH

# if you want to use the SEN12TP dataset
git clone https://github.com/oceanites/sen12tp.git
export PYTHONPATH=$PYTHONPATH:SEN12TP_REPOSITORY_PATH
```

## Training
The training scripts are located in the `scripts/train/` folder. The following scripts are available:

### NDVI
Train a MIMO U-Net with two subnetworks and `input repetition` for NDVI prediction on the SEN12TP dataset.
```bash
python train_ndvi.py \
  --dataset_dir /scratch/trossberg/sen12tp-v1-split1 \
  --checkpoint_path /ws/data/wandb_ndvi \
  --max_epochs 100 \
  --batch_size 32 \
  --num_subnetworks 2 \
  --filter_base_count 30 \
  --num_workers 30 \
  -t NDVI \
  -i VV_sigma0 \
  -i VH_sigma0 \
  --patch_size 256 \
  --stride 249 \
  --learning_rate 0.001 \
  --input_repetition_probability 0.0 \
  --loss_buffer_size 10 \
  --loss_buffer_temperature 0.3 \
  --core_dropout_rate 0.0 \
  --encoder_dropout_rate 0.0 \
  --decoder_dropout_rate 0.0 \
  --loss laplace_nll \
  --seed 1 \
  --project "MIMO NDVI Prediction"
```

### NYU Depth V2
Train a MIMO U-Net with two subnetworks and `input repetition` for depth prediction on the NYU Depth V2 dataset.
```bash
python train_nyuv2_depth.py \
  --dataset_dir /ws/data/nyuv2/depth \
  --checkpoint_path /ws/data/wandb_experiments_2 \
  --max_epochs 100 \
  --batch_size 64 \
  --num_subnetworks 2 \
  --filter_base_count 21 \
  --num_workers 50 \
  --learning_rate 0.001 \
  --input_repetition_probability 0.0 \
  --loss_buffer_size 10 \
  --loss_buffer_temperature 0.3 \
  --core_dropout_rate 0.0 \
  --encoder_dropout_rate 0.0 \
  --decoder_dropout_rate 0.0 \
  --loss laplace_nll \
  --seed 1 \
  --train_dataset_fraction 1 \
  --project "MIMO NYUv2Depth"
```

For Monte-Carlo Dropout, set `--core_dropout_rate 0.1`, `--encoder_dropout_rate 0.1`, `--decoder_dropout_rate 0.1`.

## Evaluation
The evaluation scripts are located in the `scripts/test/` folder.
These scripts evaluate a trained model on a dataset and save the results in the specified result directory.
1. `{dataset_name}_{epsilon}_inputs.npy`: Inputs to the model.
2. `{dataset_name}_{epsilon}_y_trues.npy`: Targets of the model.
3. `{dataset_name}_{epsilon}_y_preds.npy`: Predictions of the model.
4. `{dataset_name}_{epsilon}_aleatoric_vars.npy`: Aleatoric uncertainty (variance) of the model.
5. `{dataset_name}_{epsilon}_epistemic_vars.npy`: Epistemic uncertainty (variance) of the model.
6. `{dataset_name}_{epsilon}_df_pixels.csv`: Dataframe with all information above per pixel.
7. `{dataset_name}_{epsilon}_precision_recall.csv`: Dataframe for precision-recall curve.
8. `{dataset_name}_{epsilon}_calibration.csv`: Dataframe for calibration curve.


### NDVI
Evaluate a trained model for NDVI prediction on the SEN12TP dataset.
```bash
python test_ndvi.py \
  --dataset_dir PATH_TO_DATASET/test/ \
  --model_checkpoint_path PATH_TO_CHECKPOINT/model.ckpt \ 
  --result_dir PATH_TO_RESULT_DIR \
  --processes 5
```

### NYU Depth V2
Evaluate a trained model for depth prediction on the NYU Depth V2 dataset.
```bash
python test_nyuv2_depth.py \
  --model_checkpoint_paths PATH_TO_CHECKPOINT/model.ckpt \
  --dataset_dir PATH_TO_DATASET \
  --result_dir PATH_TO_RESULT_DIR \
  --processes 5
```