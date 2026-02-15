import logging
import pickle
from pathlib import Path

import mlflow
import numpy as np
from mlflow.sklearn import log_model
from mlflow.tracking import MlflowClient
from sklearn.linear_model import LogisticRegression

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_model():
    """Обучает простую модель на синтетических данных."""
    np.random.seed(42)
    # Признаки: [is_verified_seller, images_qty, description_length, category]
    X = np.random.rand(1000, 4)
    # Целевая переменная: 1 = нарушение, 0 = нет нарушения
    y = (X[:, 0] < 0.3) & (X[:, 1] < 0.2)
    y = y.astype(int)

    model = LogisticRegression()
    model.fit(X, y)
    return model


def save_model(model, path="model.pkl"):
    with open(path, "wb") as f:
        pickle.dump(model, f)


def load_model(path="model.pkl"):
    with open(path, "rb") as f:
        return pickle.load(f)


def registration_model():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("moderation-model")

    with mlflow.start_run():
        model = train_model()
        log_model(model, "model", registered_model_name="moderation-model")

    client = MlflowClient()

    # Берём последнюю версию модели
    latest_versions = client.get_latest_versions("moderation-model")  # все стадии
    latest_version = max(latest_versions, key=lambda v: int(v.version))

    # Переводим её в Production
    client.transition_model_version_stage(
        name="moderation-model",
        version=latest_version.version,
        stage="Production",
    )


def load_model_from_mlflow(model_name: str, stage: str = "Production"):
    model_uri = f"models:/{model_name}/{stage}"
    return mlflow.sklearn.load_model(model_uri)


def check_model_in_mlflow(model_name: str = "moderation-model", stage: str = "Production") -> bool:
    client = mlflow.MlflowClient()

    if stage:
        model_uri = f"models:/{model_name}/{stage}"
        try:
            model = mlflow.sklearn.load_model(model_uri)
            return model is not None
        except:
            return False
    else:
        model_versions = client.search_model_versions(f"name='{model_name}'")
        return len(model_versions) > 0


def load_or_train_model(
    use_mlflow="true",
    path="model.pkl",
    model_name: str = "moderation-model",
):
    if use_mlflow == "true":
        if not check_model_in_mlflow():
            registration_model()

        model = load_model_from_mlflow(model_name=model_name)

    else:
        model_path = Path(path)
        if model_path.exists():
            model = load_model()
            logger.info("Модель загружена")
        else:
            model = train_model()
            save_model(model)
            logger.info("Модель сохранена")
    return model
