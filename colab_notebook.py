# %% [markdown]
# # ComfyUI Colab
# Keeps session alive. Run setup via terminal:
# ```
# !git clone https://github.com/datdang-dev/comfyui-colab-setup
# !python comfyui-colab-setup/setup_env.py --hf-token=YOUR_TOKEN
# ```

# %%
#@title 🔄 Keep Alive
import time, os
from IPython.display import display, HTML

display(HTML("<h3>✅ Session active — run setup in terminal</h3>"))

while True:
    time.sleep(60)
