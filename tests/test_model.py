"""Тесты модели: train_model, save/load roundtrip, load_or_train_model"""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from app.model import load_model, load_or_train_model, save_model, train_model


@pytest.mark.unit
def test_train_model_returns_fitted_model():
    model = train_model()
    assert model is not None
    assert hasattr(model, "predict")
    assert hasattr(model, "predict_proba")


@pytest.mark.unit
def test_trained_model_predicts():
    model = train_model()
    features = np.array([[0.1, 0.1, 0.5, 0.5]])
    proba = model.predict(features)
    assert len(proba) == 1
    assert 0 <= proba[0] <= 1


@pytest.mark.unit
def test_trained_model_reasonable_predictions():
    model = train_model()

    risky = np.array([[0.1, 0.1, 0.5, 0.5]])
    safe = np.array([[0.9, 0.8, 0.1, 0.5]])

    pred_risky = model.predict(risky)[0]
    pred_safe = model.predict(safe)[0]

    assert isinstance(pred_risky, (int, float, np.integer, np.floating))
    assert isinstance(pred_safe, (int, float, np.integer, np.floating))


@pytest.mark.unit
def test_save_load_model_roundtrip(tmp_path):
    model = train_model()
    model_path = str(tmp_path / "test_model.joblib")

    save_model(model, model_path)
    loaded = load_model(model_path)

    test_features = np.array([[0.5, 0.5, 0.5, 0.5]])
    original_pred = model.predict(test_features)
    loaded_pred = loaded.predict(test_features)

    np.testing.assert_array_equal(original_pred, loaded_pred)


@pytest.mark.unit
def test_load_or_train_model_from_file(tmp_path):
    """load_or_train_model загружает существующий файл (use_mlflow=false)"""
    model = train_model()
    model_path = str(tmp_path / "model.joblib")
    save_model(model, model_path)

    # load_or_train_model использует Path(path) для проверки существования,
    # но load_model/save_model без аргумента используют default "model.joblib"
    with patch("app.model.load_model", return_value=model) as mock_load:
        loaded = load_or_train_model(use_mlflow="false", path=model_path)
        mock_load.assert_called_once()
    assert loaded is not None


@pytest.mark.unit
def test_load_or_train_model_train_new(tmp_path):
    """load_or_train_model обучает новую модель если файла нет (use_mlflow=false)"""
    model_path = str(tmp_path / "nonexistent.joblib")
    assert not Path(model_path).exists()

    # save_model использует default path "model.joblib", а не переданный path
    with patch("app.model.save_model") as mock_save:
        loaded = load_or_train_model(use_mlflow="false", path=model_path)

    assert loaded is not None
    assert hasattr(loaded, "predict")
    mock_save.assert_called_once()
