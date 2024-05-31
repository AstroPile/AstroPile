
import h5py

def _get_features(example_file_path, print_features=False):
    """
    The BTSbot dataset has ~90 features (see btsbot.py script). This is a helper
    function to quickly get the names of all features and format them so that they can
    be copied and pasted into the lists of features appearing in the btsbot.py script. 
    """
    _FLOAT_FEATURES = []
    _INT_FEATURES = []
    _BOOL_FEATURES = []
    _STRING_FEATURES = []

    with h5py.File(example_file_path, 'r') as f:
        fields = f['table'].dtype.fields
        for field in fields:
            if fields[field][0].kind == 'f':
                _FLOAT_FEATURES.append(field)
            elif fields[field][0].kind == 'i':
                _INT_FEATURES.append(field)
            elif fields[field][0].kind == 'b':
                _BOOL_FEATURES.append(field)
            elif fields[field][0].kind == 'S':
                _STRING_FEATURES.append(field)

    all_features = {
            '_FLOAT_FEATURES': _FLOAT_FEATURES, 
            '_INT_FEATURES': _INT_FEATURES,
            '_BOOL_FEATURES': _BOOL_FEATURES,
            '_STRING_FEATURES': _STRING_FEATURES
        }

    if print_features:
        for feature_set in all_features:
            print('='*100)
            print(feature_set)
            print('='*100)
            for feature in all_features[feature_set]:
                print(f'\'{feature}\',')

    return all_features
