import torch

print("torch", torch.__version__)
assert torch.cuda.is_available(), "CUDA is not available"
print("device", torch.cuda.get_device_name(0))
print("capability", torch.cuda.get_device_capability(0))
x = torch.randn(8, 3, 224, 224, device="cuda")
m = torch.nn.Conv2d(3, 16, 3, padding=1).cuda()
y = m(x)
torch.cuda.synchronize()
print("output", tuple(y.shape), y.dtype)
