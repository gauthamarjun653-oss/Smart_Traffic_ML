import torch

def verify_gpu():
    print("--- GPU Verification Status ---")
    cuda_available = torch.cuda.is_available()
    print(f"CUDA (GPU Acceleration) Available: {cuda_available}")
    if cuda_available:
        print(f"Active GPU Device Name: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Device Count: {torch.cuda.device_count()}")
        print(f"Current CUDA Device Index: {torch.cuda.current_device()}")
    else:
        print("WARNING: CUDA is not available. PyTorch will execute on CPU.")
    print("-------------------------------")

if __name__ == "__main__":
    verify_gpu()
