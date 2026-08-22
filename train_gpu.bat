@echo off
echo ======================================================================
echo  NEXUS AI - 300M Parameter Foundation Model Training on NVIDIA GPU
echo  Dataset: 100,000 Scenarios (1 Lakh) ^| Target: 20 Epochs
echo ======================================================================
echo.

python "C:\Users\Asus\Documents\far away\training\train_nexus_300m_gpu.py" --tier 300m --epochs 20 --batch-size 128 --resume

pause
