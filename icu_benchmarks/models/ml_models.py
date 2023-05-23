import gin
import lightgbm
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, Perceptron
from sklearn import svm
from icu_benchmarks.models.wrappers import MLWrapper
from sklearn.neural_network import MLPClassifier, MLPRegressor
# SKLearn models
@gin.configurable
class LGBMClassifier(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="LGBMClassifier")
    def model_args(self, *args, **kwargs):
        return lightgbm.LGBMClassifier(*args, **kwargs)


@gin.configurable
class LGBMRegressor(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="LGBMRegressor")
    def model_args(self, *args, **kwargs):
        return lightgbm.LGBMRegressor(*args, **kwargs)


@gin.configurable
class LogisticRegression(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="LogisticRegression")
    def model_args(self, *args, **kwargs):
        return LogisticRegression(*args, **kwargs)


@gin.configurable
class RFClassifier(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="RFClassifier")
    def model_args(self, *args, **kwargs):
        return RandomForestClassifier(*args, **kwargs)


@gin.configurable
class SVMClassifier(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="SVMClassifier")
    def model_args(self, *args, **kwargs):
        return svm.SVC(*args, **kwargs)

@gin.configurable
class SVMRegressor(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="SVMRegressor")
    def model_args(self, *args, **kwargs):
        return svm.SVR(*args, **kwargs)

@gin.configurable
class PerceptronClassifier(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="PerceptronClassifier")
    def model_args(self, *args, **kwargs):
        return Perceptron(*args, **kwargs)


@gin.configurable
class MLPClassifier(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="MLPClassifier")
    def model_args(self, *args, **kwargs):
        return MLPClassifier(*args, **kwargs)

class MLPRegressor(MLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = self.model_args()

    @gin.configurable(module="MLPRegressor")
    def model_args(self, *args, **kwargs):
        return MLPRegressor(*args, **kwargs)
