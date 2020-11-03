def test_search_space():
    from deephyper.nas.space.dense_skipco import create_search_space
    from random import random

    struct = create_search_space()

    ops = [random() for _ in range(struct.num_nodes)]
    struct.set_ops(ops)
    model = struct.create_model()

    from tensorflow.keras.utils import plot_model

    plot_model(model, to_file=f"test_dense_skipco.png", show_shapes=True)


if __name__ == "__main__":
    test_search_space()
