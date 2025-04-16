from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import matplotlib.pyplot as plt
import io
import numpy as np

router = APIRouter()

@router.get("/plot")
async def generate_plot(
    x_max: float = Query(10.0, description="Maximum value for the x-axis"),
    freq: float = Query(1.0, description="Frequency of the sine wave")
):
    """
    Generates a simple sine wave plot based on query parameters.
    
    - **x_max**: Sets the maximum value for the x-axis.
    - **freq**: Sets the frequency of the sine wave.
    """
    x = np.linspace(0, x_max, 400)
    y = np.sin(freq * x)

    fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.set_title(f'Sine Wave (freq={freq}, x_max={x_max})')
    ax.set_xlabel("X-axis")
    ax.set_ylabel("Y-axis")
    ax.grid(True)

    # Save the plot to a BytesIO object
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig) # Close the figure to free memory

    return StreamingResponse(buf, media_type="image/png")