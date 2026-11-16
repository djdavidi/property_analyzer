"""Offline CPU worker for the pinned OpenEarthMap semantic model.

Only this standalone worker imports optional ML dependencies. No downloaded
Python, remote inference, image upload or automatic model download is executed.
"""

import sys


def main():
    import numpy as np
    import torch
    import segmentation_models_pytorch as smp

    weights, input_path, output_path = sys.argv[1:]
    torch.set_num_threads(2)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    model = smp.Unet(
        classes=9,
        activation=None,
        encoder_weights=None,
        encoder_name="efficientnet-b4",
        decoder_attention_type="scse",
    )
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    model.eval()
    image = np.load(input_path, allow_pickle=False)
    if image.ndim != 3 or image.shape[2] != 3 or image.shape[0] * image.shape[1] > 1_000_000:
        raise ValueError("Invalid bounded model input")
    height, width = image.shape[:2]
    size = 512
    stride = 384
    # Overlapping windows avoid a single image resize and average seam predictions.
    ys = list(range(0, max(height - size, 0) + 1, stride))
    xs = list(range(0, max(width - size, 0) + 1, stride))
    if ys[-1] != max(height - size, 0):
        ys.append(max(height - size, 0))
    if xs[-1] != max(width - size, 0):
        xs.append(max(width - size, 0))
    probabilities = np.zeros((9, height, width), dtype="float32")
    counts = np.zeros((height, width), dtype="float32")
    with torch.inference_mode():
        for y in ys:
            for x in xs:
                patch = image[y : y + size, x : x + size]
                h, w = patch.shape[:2]
                padded = np.pad(patch, ((0, size - h), (0, size - w), (0, 0)), mode="edge")
                tensor = (
                    torch.from_numpy(padded.transpose(2, 0, 1).copy()).unsqueeze(0).float() / 255
                )
                prediction = model(tensor).softmax(1)[0].numpy()[:, :h, :w]
                probabilities[:, y : y + h, x : x + w] += prediction
                counts[y : y + h, x : x + w] += 1
    probabilities /= counts[None, :, :]
    labels = probabilities.argmax(0).astype("uint8")
    ordered = np.partition(probabilities, -2, axis=0)
    # Scores are not calibrated confidence intervals; uncertain pixels stay unknown.
    labels[(ordered[-1] < 0.60) | ((ordered[-1] - ordered[-2]) < 0.15)] = 0
    np.save(output_path, labels, allow_pickle=False)


if __name__ == "__main__":
    main()
