import datetime
import pandas as pd
from src.models.model import *
from hyperopt import Trials, STATUS_OK, tpe, fmin, hp
from hyperas.utils import eval_hyperopt_space
from keras.optimizers import SGD
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, recall_score, precision_score, f1_score
from src.helpers.preprocess_helpers import Standardizer
from src.helpers.import_helpers import LoadDataset, SplitData


X, y = LoadDataset('final_binned_global.csv', directory='data//processed//')

# Split data
X_train, y_train, X_test, y_test = SplitData(X,y, test_size=0.1)

# Standardize training data
X_train = Standardizer().standardize(X_train, na_values=False)
X_test = Standardizer().standardize(X_test, na_values=False)

# Save the split train and test dataset before optimization for future reference
y_train_save = pd.DataFrame(y_train, columns=['LABEL'])
X_train_save = pd.DataFrame(X_train.astype(np.float))
y_test_save = pd.DataFrame(y_test, columns=['LABEL'])
X_test_save = pd.DataFrame(X_test.astype(np.float))

X_train_save.to_pickle('data//split//globalbinneddata_XTRAIN.pkl')
y_train_save.to_pickle('data//split//globalbinneddata_YTRAIN.pkl')
X_test_save.to_pickle('data//split//globalbinneddata_XTEST.pkl')
y_test_save.to_pickle('data//split//globalbinneddata_YTEST.pkl')


cnn_space = {

        'nb_blocks': hp.choice('nb_blocks', [0,1,2,3]),
        'filters': hp.choice('filters', [8,16,32,64,128,254]),
        'kernel_size':  hp.choice('kernel_size', [3, 5, 7, 9]),
        'pooling': hp.choice('pooling', ['max','average']),
        'pooling_size': hp.choice('pooling_size', [2,3,4]),
        'pooling_strides': hp.choice('pooling_strides', [2,3,4]),
        'conv_dropout': hp.uniform('conv_dropout', 0.0, 0.35),
        'fc_dropout': hp.uniform('fc_dropout', 0.0,0.6),
        'fc_units': hp.choice('fc_units', [32,64,128,254]),
        'batch_size' : hp.choice('batch_size', [16,32]),
        'lr_rate_mult': hp.loguniform('lr_rate_mult', -0.5, 0.5),
        'momentum': hp.choice('momentum', [0, 0.25, 0.4]),
        'batch_norm': hp.choice('batch_norm', [True, False]),

        'nb_epochs' :  hp.uniform('nb_epochs', 5.0, 50.0),
        'activation': 'prelu'
        }


def create_cnn_model(params):

    start_time = time.time()

    cnn = CNN_Model(output_dim=1, sequence_length=X_train.shape[1], nb_blocks=params['nb_blocks'], filters=params['filters'],
                    kernel_size=params['kernel_size'],
                    activation=params['activation'], pooling=params['pooling'], pool_size=params['pooling_size'],
                    pool_strides=params['pooling_strides'],
                    conv_dropout=params['conv_dropout'], fc_dropout=params['fc_dropout'], dense_units=params['fc_units'], batch_norm=params['batch_norm'])

    cnn.Build()

    cnn.Compile(loss='binary_crossentropy', optimizer=SGD(lr= 0.001 * params['lr_rate_mult'], momentum=params['momentum'], decay=0.0001,
                          nesterov=True), metrics=['accuracy'])

    nb_epochs = int(params['nb_epochs'])
    print('Number of Epochs: ', nb_epochs)
    batch_size = params['batch_size']

    # define 10-fold cross validation test harness
    kfold = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)

    cvscores = []

    for train_index, valid_index in kfold.split(X_train, y_train):

        X_train_fold = X_train[train_index]
        X_valid_fold = X_train[valid_index]
        y_train_fold = y_train.iloc[train_index]
        y_valid_fold = y_train.iloc[valid_index]

        # Reshape data to 3D input
        X_train_fold = X_train_fold.reshape(X_train_fold.shape[0], X_train_fold.shape[1], 1)
        # X_val = X_val.reshape(X_val.shape[0], X_val.shape[1], 1)
        X_valid_fold = X_valid_fold.reshape(X_valid_fold.shape[0], X_valid_fold.shape[1], 1)

        #reduceLR = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=0.0001, verbose=1)
        #earlyStopping = EarlyStopping(monitor='val_loss', min_delta=0, patience=10, mode='auto')
        cnn.FitData(X_train=X_train_fold, y_train=y_train_fold, batch_size = batch_size, nb_epochs = nb_epochs, verbose = 2)
        #cnn.FitDataWithValidationCallbacks(X_train=X[train], y_train=y[train], X_val=X[valid], y_val=y[valid],
        #                                   batch_size=batch_size, nb_epochs=50, verbose=2, cb1=earlyStopping)

        score, acc = cnn.Evaluate(X_valid_fold, y_valid_fold, batch_size, verbose=0)

        Y_score, Y_predict, Y_true = cnn.Predict(X_valid_fold, y_valid_fold)
        recall = recall_score(y_valid_fold, Y_predict)
        precision = precision_score(y_valid_fold, Y_predict)
        f1 = f1_score(y_valid_fold, Y_predict)

        auc = roc_auc_score(y_valid_fold, Y_score)

        print('ROC/AUC Score: ', auc)
        print('Precision: ',precision )
        print('Recall: ', recall)

        print('\n')

        cvscores.append(auc)


    print("CV Score: %.2f%% (+/- %.2f%%)" % (np.mean(cvscores), np.std(cvscores)))

    total_seconds = time.time() - start_time
    print('CV Time: ', str(datetime.timedelta(seconds=total_seconds)) )

    return {'loss': -auc, 'status': STATUS_OK}





lstm_space = {

        'nb_lstm_layers': hp.choice('nb_lstm_layers', [0,1]),
        'lstm_units': hp.choice('lstm_units', [2, 5, 10, 15]),

        'dropout': hp.uniform('dropout', 0.0, 0.5),
        'fc_units': hp.choice('fc_units', [32,64,128]),
        'fc_layers': hp.choice('fc_layers', [0, 1, 2]),


        'batch_size' : hp.choice('batch_size', [16,32,64]),
        'lr_rate_mult': hp.loguniform('lr_rate_mult', -0.5, 0.5),
        'momentum': hp.choice('momentum', [0, 0.25, 0.4]),
        'batch_norm': hp.choice('batch_norm', [True, False]),
        'nb_epochs' :  hp.uniform('nb_epochs', 10.0, 50.0),
        'activation': hp.choice('activation', ['prelu', 'relu'])
        }


def create_lstm(params):

    lstm = LSTM_Model(output_dim=1, sequence_length=X_train.shape[1],
                    nb_lstm_layers=params['nb_lstm_layers'], nb_lstm_units=params['lstm_units'], nb_fc_layers=params['fc_layers'], nb_fc_units=params['fc_units'],
                    activation=params['activation'],
                    dropout=params['dropout'], batch_normalisation=params['batch_norm'])

    lstm.Build()


    print('LR Multiplier: ', params['lr_rate_mult'])
    print('Momentum: ', params['momentum'])

    lstm.Compile(loss='binary_crossentropy',
                optimizer=SGD(lr=0.001 * params['lr_rate_mult'], momentum=params['momentum'], decay=0.0001,
                              nesterov=True), metrics=['accuracy'])

    nb_epochs = int(params['nb_epochs'])
    batch_size = params['batch_size']
    print('Number of Epochs: ', nb_epochs)
    print('Batch Size: ', batch_size)

    start_time = time.time()

    # define 10-fold cross validation test harness
    kfold = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)

    cvaucscores = []
    cvf1scores = []
    cvrecallscores = []
    cvprecisionscores = []

    for train_index, valid_index in kfold.split(X_train, y_train):
        X_train_fold = X_train[train_index]
        X_valid_fold = X_train[valid_index]
        y_train_fold = y_train.iloc[train_index]
        y_valid_fold = y_train.iloc[valid_index]

        # Reshape data to 3D input
        X_train_fold = X_train_fold.reshape(X_train_fold.shape[0], X_train_fold.shape[1], 1)
        # X_val = X_val.reshape(X_val.shape[0], X_val.shape[1], 1)
        X_valid_fold = X_valid_fold.reshape(X_valid_fold.shape[0], X_valid_fold.shape[1], 1)

        # reduceLR = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=0.0001, verbose=1)
        # earlyStopping = EarlyStopping(monitor='val_loss', min_delta=0, patience=10, mode='auto')
        lstm.FitData(X_train=X_train_fold, y_train=y_train_fold, batch_size=batch_size, nb_epochs=nb_epochs, verbose=2)
        # cnn.FitDataWithValidationCallbacks(X_train=X[train], y_train=y[train], X_val=X[valid], y_val=y[valid],
        #                                   batch_size=batch_size, nb_epochs=50, verbose=2, cb1=earlyStopping)

        score, acc = lstm.Evaluate(X_valid_fold, y_valid_fold, batch_size, verbose=0)

        Y_score, Y_predict, Y_true = lstm.Predict(X_valid_fold, y_valid_fold)
        recall = recall_score(y_valid_fold, Y_predict)
        precision = precision_score(y_valid_fold, Y_predict)
        auc = roc_auc_score(y_valid_fold, Y_score)
        f1 = f1_score(y_valid_fold, Y_predict)

        print('Accuracy: ', acc)
        print('ROC/AUC Score: ', auc)
        print('Precision: ', precision)
        print('Recall: ', recall)
        print('F1 Score: ', f1)
        print('\n')

        cvaucscores.append(auc)
        cvf1scores.append(f1)
        cvprecisionscores.append(precision)
        cvrecallscores.append(recall)

    print("CV AUC Score: %.2f%% (+/- %.2f%%)" % (np.mean(cvaucscores), np.std(cvaucscores)))
    print("CV Precision Score: %.2f%% (+/- %.2f%%)" % (np.mean(cvprecisionscores), np.std(cvprecisionscores)))
    print("CV Recall Score: %.2f%% (+/- %.2f%%)" % (np.mean(cvrecallscores), np.std(cvrecallscores)))
    print("CV F1 Score: %.2f%% (+/- %.2f%%)" % (np.mean(cvf1scores), np.std(cvf1scores)))


    total_seconds = time.time() - start_time
    print('CV Time: ', str(datetime.timedelta(seconds=total_seconds)))

    return {'loss': -auc, 'status': STATUS_OK}




def run_trials(model_type, evals=5):


    trials_step = 1
    max_trials = evals

    trials_filename = model_type + "_trials" + ".hyperopt"

    # Try loading existing trials object for model type
    try:
        trials = pickle.load(open("models//trials//" + trials_filename, "rb"))
        print("Found saved Trials! Loading...")
        max_trials = len(trials.trials) + trials_step
        print("Rerunning from {} trials to {} (+{}) trials.".format(len(trials.trials), max_trials, trials_step))

    except:
        trials = Trials()


    start_time = time.time()


    if model_type == 'cnn':
        best_model = fmin(create_cnn_model, cnn_space, algo=tpe.suggest, max_evals=max_trials, trials=trials)
        print("Best CNN:", best_model)
        best_model_config = eval_hyperopt_space(lstm_space, best_model)

    elif model_type == 'lstm':
        best_model = fmin(create_lstm, lstm_space, algo=tpe.suggest, max_evals=max_trials, trials=trials)
        print("Best LSTM:", best_model)
        best_model_config = eval_hyperopt_space(lstm_space, best_model)

    elif model_type == 'mlp':
        # TODO - Optimize MLP
        print('N/A')


    total_seconds = time.time() - start_time
    print('Hyperparameter Optimization Time: ', str(datetime.timedelta(seconds=total_seconds)) )
    print('')


    # json.dump(best_run, open("models/best_run.txt", 'w'))


    print ('Best Configuration: ', best_model_config)


    return best_model_config