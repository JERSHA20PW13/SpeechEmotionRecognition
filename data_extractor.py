import numpy as np
import pandas as pd
import os
import tqdm
from collections import defaultdict

from utils import get_label, get_first_letters, extract_feature

class AudioExtractor:
    def __init__(self, audio_config=None, verbose=1, features_folder_name="features",
                    emotions=['sad', 'neutral', 'happy'], balance=True):
        self.audio_config = audio_config if audio_config else {'mfcc': True, 'chroma': True, 'mel': True, 'contrast': False, 'tonnetz': False}
        self.verbose = verbose
        self.features_folder_name = features_folder_name
        self.emotions = emotions
        self.balance = balance
        self.input_dimension = None

    def _load_data(self, desc_files, partition, shuffle):
        self.load_metadata_from_desc_file(desc_files, partition)
        
        # balancing the datasets ( both training or testing )
        if partition == "train" and self.balance:
            self.balance_training_data()
        elif partition == "test" and self.balance:
            self.balance_testing_data()
        else:
            if self.balance:
                raise TypeError("Invalid partition, must be either train/test")
        
        if shuffle:
            self.shuffle_data_by_partition(partition)

    def load_train_data(self, desc_files=["train_speech.csv"], shuffle=False):
        self._load_data(desc_files, "train", shuffle)
        
    def load_test_data(self, desc_files=["test_speech.csv"], shuffle=False):
        self._load_data(desc_files, "test", shuffle)

    def shuffle_data_by_partition(self, partition):
        if partition == "train":
            self.train_audio_paths, self.train_emotions, self.train_features = shuffle_data(self.train_audio_paths,
            self.train_emotions, self.train_features)
        elif partition == "test":
            self.test_audio_paths, self.test_emotions, self.test_features = shuffle_data(self.test_audio_paths,
            self.test_emotions, self.test_features)
        else:
            raise TypeError("Invalid partition, must be either train/test")

    def load_metadata_from_desc_file(self, desc_files, partition):
        # combining all dataframes
        df = pd.DataFrame({'path': [], 'emotion': []})
        
        for desc_file in desc_files:
            df = pd.concat((df, pd.read_csv(desc_file)), sort=False)
        
        if self.verbose:
            print("[*] Loading audio file paths and its corresponding labels...")
        
        audio_paths, emotions = list(df['path']), list(df['emotion'])
        
        if not os.path.isdir(self.features_folder_name):
            os.mkdir(self.features_folder_name)
        
        label = get_label(self.audio_config)
        
        n_samples = len(audio_paths)
        first_letters = get_first_letters(self.emotions)
        
        name = os.path.join(self.features_folder_name, f"{partition}_{label}_{first_letters}_{n_samples}.npy")
        if os.path.isfile(name):
            if self.verbose:
                print("[+] Feature file already exists, loading...")
            features = np.load(name)
        else:
            features = []
            append = features.append
            
            # for terminal progress bars
            for audio_file in tqdm.tqdm(audio_paths, f"Extracting features for {partition}"):
                feature = extract_feature(audio_file, **self.audio_config)
                if self.input_dimension is None:
                    self.input_dimension = feature.shape[0]
                append(feature)
            # convert to numpy array
            features = np.array(features)
            # save it
            np.save(name, features)
        if partition == "train":
            try:
                self.train_audio_paths
            except AttributeError:
                self.train_audio_paths = audio_paths
                self.train_emotions = emotions
                self.train_features = features
            else:
                if self.verbose:
                    print("[*] Adding additional training samples")
                self.train_audio_paths += audio_paths
                self.train_emotions += emotions
                self.train_features = np.vstack((self.train_features, features))
        
        elif partition == "test":
            try:
                self.test_audio_paths
            except AttributeError:
                self.test_audio_paths = audio_paths
                self.test_emotions = emotions
                self.test_features = features
            else:
                if self.verbose:
                    print("[*] Adding additional testing samples")
                self.test_audio_paths += audio_paths
                self.test_emotions += emotions
                self.test_features = np.vstack((self.test_features, features))
        
        else:
            raise TypeError("Invalid partition, must be either train/test")

    def _balance_data(self, partition):
        if partition == "train":
            emotions = self.train_emotions
            features = self.train_features
            audio_paths = self.train_audio_paths
        elif partition == "test":
            emotions = self.test_emotions
            features = self.test_features
            audio_paths = self.test_audio_paths
        else:
            raise TypeError("Invalid partition, must be either train/test")
        
        count = []
        

        for emotion in self.emotions:
            count.append(len([ e for e in emotions if e == emotion]))

        # get the minimum data samples to balance to
        minimum = min(count)
        if minimum == 0:
            # won't balance, otherwise 0 samples will be loaded
            print("[!] One class has 0 samples, setting balance to False")
            self.balance = False
            return
        if self.verbose:
            print("[*] Balancing the dataset to the minimum value:", minimum)
        
        d = defaultdict(list)
        
        counter = {e: 0 for e in self.emotions }

        for emotion, feature, audio_path in zip(emotions, features, audio_paths):
            if counter[emotion] >= minimum:
                # minimum value exceeded
                continue
            counter[emotion] += 1
            d[emotion].append((feature, audio_path))

        emotions, features, audio_paths = [], [], []
        for emotion, features_audio_paths in d.items():
            for feature, audio_path in features_audio_paths:
                emotions.append(emotion)
                features.append(feature)
                audio_paths.append(audio_path)
        
        if partition == "train":
            self.train_emotions = emotions
            self.train_features = features
            self.train_audio_paths = audio_paths
        elif partition == "test":
            self.test_emotions = emotions
            self.test_features = features
            self.test_audio_paths = audio_paths
        else:
            raise TypeError("Invalid partition, must be either train/test")


    def balance_training_data(self):
        self._balance_data("train")

    def balance_testing_data(self):
        self._balance_data("test")

def shuffle_data(audio_paths, emotions, features):
    p = np.random.permutation(len(audio_paths))
    audio_paths = [audio_paths[i] for i in p] 
    emotions = [emotions[i] for i in p]
    features = [features[i] for i in p]
    return audio_paths, emotions, features

def load_data(train_desc_files, test_desc_files, audio_config=None, shuffle=True,
                balance=True, emotions=['sad', 'neutral', 'happy']):

    audiogen = AudioExtractor(audio_config=audio_config, emotions=emotions,
                                balance=balance, verbose=0)

    audiogen.load_train_data(train_desc_files, shuffle=shuffle)

    audiogen.load_test_data(test_desc_files, shuffle=shuffle)

    return {
        "X_train": np.array(audiogen.train_features),
        "X_test": np.array(audiogen.test_features),
        "y_train": np.array(audiogen.train_emotions),
        "y_test": np.array(audiogen.test_emotions),
        "train_audio_paths": audiogen.train_audio_paths,
        "test_audio_paths": audiogen.test_audio_paths,
        "balance": audiogen.balance,
    }