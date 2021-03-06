'''
Created on May 31, 2013

@author: Bhushan Ramnani
@Description: key stroke data analysis by taking each turn as a training example with mean dwell time, ud latency and down-down latency
'''

import sys
import numpy as np
from sklearn.naive_bayes import GaussianNB,BernoulliNB 
from sklearn import cross_validation
import xlrd as xl
import MySQLdb as mdb
import csv
import math
from scipy import interp
import pylab as pl
from sklearn.metrics import roc_curve, auc
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.colors import ListedColormap
from mayavi import mlab
from sklearn.dummy import DummyClassifier



labelsList = ["QUESTION", "AGREE_CANDIDATE", "AGREEMENT", "EXPLANATION_CONTRIBUTION", "POSITIVITY", "GIVING_OPINION", "PREDICTION_CONTRIBUTION","HELP_REQUEST","REVOICABLE","DISAGREEMENT","CHALLENGE_CONTRIBUTION","EXPLANATION_REQUEST"]


def xlToNpArray(fileName):
    """Takes an excel file and returns a numpy array consisting of the relevant data. Also returns an array consisting of labels for each point"""
    wb = xl.open_workbook(fileName)
    S = wb.sheet_by_index(0)
    data = np.empty((S.nrows,3))
    labels = []
    for i in xrange(S.nrows):
        A = S.row_values(i)
        data[i] = [float(A[2]),float(A[3]),float(A[4])]
        if A[5]=="NEGATIVE_EXAMPLE":
            labels.append(0)
        else:
            labels.append(1)
    labels = np.array(labels)
    return data,labels


def csvToNpArray(fileName):
    """Takes a csv file and returns a numpy array consisting of the relevant data. Also returns an array consisting of labels for each point"""
    fileToOpen = open(fileName)
    reader = csv.reader(fileToOpen)
    number_of_records = 0
    for row in reader:
        number_of_records += 1
    fileToOpen.close() 
    
    fileToOpen = open(fileName)
    reader = csv.reader(fileToOpen)
    data = np.empty((number_of_records,3))
    labels = []
    i = 0
    for row in reader:
        data[i] = [float(row[2]),float(row[3]),float(row[4])]
        if row[5]=="NEGATIVE_EXAMPLE":
            labels.append(0)
        else:
            labels.append(1)
        i = i+1
        
    fileToOpen.close()
    labels = np.array(labels)
    return data,labels


def extractFromDatabase(query):
    """Takes a sql squery. Returns data(num_of_samples*features) numpy matrix, the labels numpy array, exampleCounts dictionary as a result"""
    try:
        con = mdb.connect(host="PL09-McKinley",port=3310,user="Bhushan",passwd="changeme",db="bhushan")
        cur = con.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        
    except mdb.Error, e:
      
        print "Error %d: %s" % (e.args[0],e.args[1])
        sys.exit(1)
        
    finally:            
        if con:    
            con.close()
    
    exampleCounts = {}
    numPositives = 0
    numNegatives = 0
    number_of_records = len(rows)
    data = np.empty((number_of_records,3)) #Stores meanDwellTime, mean upDown and mean downDown latency
    metadata = np.empty((number_of_records,2)) #stores turn id and username in the 0th and the 1st column respectively    
    labels = []
    i = 0
    for row in rows:
        metadata[i] = [row[0],row[1]]    
        data[i] = [float(row[2]),float(row[3]),float(row[4])]
        if row[5]=="NEGATIVE_EXAMPLE":
            labels.append(0)
            numNegatives += 1
        else:
            labels.append(1)
            numPositives += 1
        i = i+1
    exampleCounts["Number_of_positives"] = numPositives
    exampleCounts["Number_of_negatives"] = numNegatives
    exampleCounts["Total_number_of_examples"] = numPositives + numNegatives
    labels = np.array(labels)
    return data,labels, exampleCounts,metadata



def dataFromLabel(label):
    """REQUIRES: label as a string.
       ENSURES : Returns data(num_of_samples*features) numpy matrix, the labels numpy array and the exampleCounts dictionary as a result"""
    
    query = "CALL sp_generateDataNormalizedZscoreStudentOnly('"+label+"')"
    return extractFromDatabase(query)



def normalizeByStudentZscore(metadata,data,train,test):
    """REQUIRES: metadata: turnId and the username information
                data: the data itself
                train: training indices
                test: testing indices
        ENSURES: returns training and test data as a numpy matrix after normalization by student"""
    
    trainData = data[train]
    testData = data[test]
    trainMetadata = metadata[train]
    testMetadata = metadata[test]
    students = {} #key: student name, value : tuple of three lists, A, B and C. A:list of dwell times. B:list of up down latency, C

    for i in xrange(len(train)):
        studentName = trainMetadata[i][1]
        if studentName in students:
            (A,B,C) = students[studentName]
            students[studentName] = (A.append(trainData[i][0]), B.append(trainData[i][1]), C.append(trainData[i][1]))


def generateROCCurveAndReturnAUC(metadata,label,classifier,data,target,cv,generateCurve):
    """If generateCurve is true, only then the curve will be plotted, else only the auc value will be returned"""
    ###############################################################################
    # Classification and ROC analysis
    
    # Run classifier with crossvalidation and plot ROC curves
    ###############################################################################
    
    mean_tpr = 0.0
    mean_fpr = np.linspace(0, 1, 100)
    all_tpr = []
    
    
    for i, (train, test) in enumerate(cv):
        #(train_matrix,test_matrix) = normalizeByZscore(data[train],data[test])
        
        #trainData, testData = normalizeByStudentZscore(metadata,data,train,test)
        probas_ = classifier.fit(data[train], target[train]).predict_proba(data[test])
        # Compute ROC curve and area the curve
        fpr, tpr, thresholds = roc_curve(target[test], probas_[:, 1])
        mean_tpr += interp(mean_fpr, fpr, tpr)
        mean_tpr[0] = 0.0
        roc_auc = auc(fpr, tpr)
        if generateCurve:
            pl.plot(fpr, tpr, lw=1, label='ROC fold %d (area = %0.2f)' % (i, roc_auc))
    
    if generateCurve:
        pl.plot([0, 1], [0, 1], '--', color=(0.6, 0.6, 0.6), label='Luck')
    
    mean_tpr /= len(cv)
    mean_tpr[-1] = 1.0
    mean_auc = auc(mean_fpr, mean_tpr)
    
    if generateCurve:
        pl.plot(mean_fpr, mean_tpr, 'k--',
                label='Mean ROC (area = %0.2f)' % mean_auc, lw=2)
        pl.xlim([-0.05, 1.05])
        pl.ylim([-0.05, 1.05])
        pl.xlabel('False Positive Rate')
        pl.ylabel('True Positive Rate')
        pl.title('ROC Curve. Gaussian Naive Bayes. '+label+'.')
        pl.legend(loc="lower right")
        pl.savefig('ROC_'+label+'_GNB_Original.png')
        pl.clf()
        
    return mean_auc


def calculateZStatistic(aucValue,label,data,target,kfold):
    """Used to test the statistical sifnificance of an AUC value generated by a trained classifier. Performs a 20000 bootstrap replication by
    repeating the experiment on untrained classifier 2000 times"""
    """REQUIRES: classifier: untrained classifier object 
                 auc: auc value to be tested
                 data: data to be trained
                 target: target of the training examples
                 kfold: folds generated by a cross-validation function"""
    """ENSURES: returns a z-statistic used to test the statistical significance of the auc value"""
 
    auc_values = []
    classifier = DummyClassifier(strategy='stratified',random_state=0)
    bs = cross_validation.StratifiedShuffleSplit(y = target, n_iter = 2000, train_size = 0.75, indices = True)
    for train, test in bs:
        probas_ = classifier.fit(data[train], target[train]).predict_proba(data[test])
    # Compute ROC curve and area the curve
        fpr, tpr, thresholds = roc_curve(target[test], probas_[:, 1])
        roc_auc = auc(fpr, tpr)
        auc_values.append(roc_auc)
    
    #aucTemp = generateROCCurveAndReturnAUC(label,classifier,data,target,kfold,generateCurve = False)
    
    mean = np.mean(auc_values)
    stdDev = np.std(auc_values)
    z = (aucValue-mean)/stdDev
    return z
    
    

def classifyAll():
    f = open("analysisResults.txt", "r+")
    f.write("Label\tMean Accuracy\tAUC\tZStatistic\tNumber_Of_Positives\tNumber_Of_Negatives\tTotal\n")
    
    for label in labelsList:
        (data,target,exampleCounts,metadata) = dataFromLabel(label)
        #collecting all training data in rows    
        gnb = GaussianNB()
        
        kfold = cross_validation.StratifiedKFold(target, n_folds=4)
        #kfold = cross_validation.KFold(len(data), n_folds=3)
        auc = generateROCCurveAndReturnAUC(metadata,label,gnb,data,target,kfold,generateCurve = True)
        zStatistic = calculateZStatistic(auc,label,data,target,kfold)
        accuracy = [gnb.fit(data[train], target[train]).score(data[test], target[test]) for train, test in kfold]
        f.write(label+"\t"+str(np.mean(accuracy))+"\t"+str(auc)+"\t"+str(zStatistic)+"\t"+str(exampleCounts["Number_of_positives"])+"\t"+str(exampleCounts["Number_of_negatives"])+"\t"+str(exampleCounts["Total_number_of_examples"])+"\n")
    #print cross_validation.cross_val_score(gnb, data, target, cv=kfold)
    f.close()



def main():
    for label in labelsList:
        (data,target,exampleCounts) = dataFromLabel(label)
        target = target + 1
        pts = mlab.points3d(data[:,0],data[:,1],data[:,2],target)
        mlab.show()
        #fig = pl.figure()
        #ax = fig.add_subplot(111, projection='3d')
        #cm_bright = ListedColormap(['#FF0000', '#0000FF'])
        #target.astype(float)
        #pl.title('Scatter Plot for separability. '+label+'.')
        #ax.scatter(data[:,0],data[:,1],data[:,2],c=target,cmap=cm_bright)
        #pl.scatter(data[:,0],data[:,2],c=target,cmap=cm_bright)
        #pl.show()
    
    

    
    
    
    
    
    
classifyAll()    
    
    
    
    
    
if __name__ == '__main__':
    pass


