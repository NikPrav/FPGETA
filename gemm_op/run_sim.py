import torch
import torch.nn as nn
from torch.autograd import Variable

from memory_handler import DRAM
from layer_nodes import LayerNode
from compiler import GEMMCompiler, SystolicArrayParams
from padding import padding_func

x = Variable(torch.randn(1,7,7))

x = torch.tensor([[1,2,3,4,5,6],[7,8,9,10,11,12],[13,14,15,16,17,18]], dtype=torch.float16)


# Initialize an empty list to store the layer info objects
node_list = []

# Create the model
model = nn.Sequential(nn.Linear(6, 4, dtype=torch.float16), nn.Linear(4, 16, dtype=torch.float16))

output = model(x)
print(output.size())

# Setting Systolic Array Parameters
R, C = 4, 4  # Size of the systolic array
mem_size = 1096*1096  # Memory size of the FPGA
data_size = 16
i_buf_size = 16*data_size  # Input buffer size of the FPGA
w_buf_size = i_buf_size  # Weight buffer size of the FPGA
o_buf_size = R*C*data_size  # Output buffer size of the FPGA

sys_params = SystolicArrayParams(R, C, mem_size, i_buf_size, w_buf_size, o_buf_size, data_size)

model[0].weight = nn.Parameter(data=torch.tensor([[1,2,3,4,5,6],[7,8,9,10,11,12],[13,14,15,16,17,18], [19, 20, 21, 22, 23, 24]], dtype=torch.float16))
# model[1].weight = nn.Parameter(data=torch.tensor([[1,2,3,4],[5,6,7,8],[9,10,11,12], [13,14,15,16]], dtype=torch.float16))


# Loop through each layer in the model and padding
for name, layer in model.named_children():
    if isinstance(layer, torch.nn.modules.conv.Conv2d) or isinstance(layer, torch.nn.modules.linear.Linear):
        new_node = LayerNode(name,layer, x)
        padded_node = padding_func(new_node,sys_params)
        node_list.append(padded_node)
        x = layer(x)


# Create 1D DRAM array representation with instructions and memory
Dram_content = DRAM(mem_size)
w_ptr_end = Dram_content.mem_init(node_list, sys_params)

i_ptr_cur = w_ptr_end
w_ptr_cur = sys_params.inst_mem

instuction_list = []

for node in node_list:
    M = node.input_size[-2]
    N = node.input_size[-1]
    K = node.weight_size[-2]

    gemm = GEMMCompiler(M, N, K, sys_params, i_ptr_cur, w_ptr_cur, w_ptr_end)

    instructions, i_ptr_cur = gemm.compile_matrices() 
    instuction_list.append(instructions)
    w_ptr_cur = w_ptr_cur + node.weight_size[0]*node.weight_size[1]*sys_params.data_size

print(x)