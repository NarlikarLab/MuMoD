from cstructures import *
import multiprocessing as mp
import multiprocessing.sharedctypes as mpc
import pickle
import time
import saveFiles as sf

lock = mp.Lock()
lockL = mp.Lock()
v = mp.Value('i', 0)

# function to call c function trainOut 
def singleEval(args):
    try:
        pickleFile = args[1]
        mode = args[3].value
        seed = args[7].value
        args = args[2:]
        to = libctest.trainData(*args)
        toPy = getTrainOut(to, mode, args[0].contents.n)
        x = libctest.freeTo(to)
        lockL.acquire()
        lock.acquire()
        t = pickle.dump((mode, toPy, seed), open(pickleFile, "wb"))
        v.value = 1
        lock.release()
    except (KeyboardInterrupt, SystemExit):
        exit(1)


# get the path of the likelihood file likes.txt when -v is set to 1
def getLikesNames(params, d):
    if d['-v'] == 0: return "0"
    return d['-o'][1] + "/mode_" + str(params[0]) + "/Trial_" + str(params[1]) + "/likes.txt"

# call the singleEval() function on multiple models by parallelisation
def multiEval(d, ds, background, pickleFile):

    # create lists of number of models to learn
    trainOut = map(lambda x: 0, range(d['-maxMode'] - d['-minMode'] + 1))
    modelSeeds = map(lambda x: 0, range(d['-maxMode'] - d['-minMode'] + 1))
    seeds = map(lambda x: x + 1, range(d['-lcount']))
    params = sum(map(lambda x: map(lambda y: (x, y), seeds), range(d['-minMode'], (d['-maxMode'] + 1))), [])
    counts = [0 for i in range(d['-maxMode'] - d['-minMode'] + 1)]

    nmodels = len(params)
    joined = 0
    started = 0
    pc = min(nmodels, d['-proc'])
    procArr = map(lambda x: 0, range(pc))
    p = map(lambda x: 0, range(pc))

    # loop over the number of models to learn and parallelise it up to the value of nproc
    try:
        while joined < nmodels:
            time.sleep(0.5)
            for j in range(pc):
                if procArr[j] != 0:
                    if not p[j].is_alive():
                        p[j].join()
                        procArr[j] = 0
                        joined = joined + 1
                if procArr[j] == 0 and started < nmodels:
                    print "Starting mode", params[started][0], "seed", params[started][1]
                    pr = mp.Process(target = singleEval, args = ([lock, pickleFile, ds, c_int(params[started][0]), c_float(d['-a']), c_float(d['-lambda']), c_double(d['-zoops']), c_uint(params[started][1]), background, getCArray([d['-initialWidth'] for i in range(params[started][0])], c_int), c_int(d['-minWidth']), getLikesNames(params[started], d)], ))
                    p[j] = pr
                    p[j].start()
                    procArr[j] = params[joined][0]
                    started = started + 1

                lock.acquire()
                with open(pickleFile, "rb") as f:
                    tmp = pickle.load(f)
                    # check if an execution is complete and then save details
                    if tmp != []:
                        print "Finished one of mode", tmp[0]
                        sf.saveModeTrialDetails(d, tmp[1], tmp[2], tmp[0])
                        counts[tmp[0] - d['-minMode']] = counts[tmp[0] - d['-minMode']] + 1
                        if trainOut[tmp[0] - d['-minMode']] == 0 or trainOut[tmp[0] - d['-minMode']]['likelihood'] < tmp[1]['likelihood']:
                            trainOut[tmp[0] - d['-minMode']] = tmp[1]
                            modelSeeds[tmp[0] - d['-minMode']] = tmp[2]
                        if counts[tmp[0] - d['-minMode']] == d['-lcount']:
                            sf.saveModeDetails(d, trainOut[tmp[0] - d['-minMode']], modelSeeds[tmp[0] - d['-minMode']], tmp[0])
                    if v.value == 1:
                        lockL.release()
                        v.value = 0
                pickle.dump([], open(pickleFile, "wb"))
                lock.release()

    except (KeyboardInterrupt, SystemExit):
        for i in p: 
            if type(i) is int: continue
            i.terminate()
            i.join()
        exit(1)

    print "All joined!!"
    return zip(trainOut, modelSeeds)


def learn(d):
    mode = 4
    seed = 1
    likeFile = d['-o'][1] + "/likes.txt"
    outfile = d['-o'][1] + "/test.txt"
    pickleFile = d['-o'][1] + "/tmpfile.p"
    pickle.dump([], open(pickleFile, "wb"))

    # call c function getData to read the FASTA file into a structure
    ds = mpc.copy(libctest.getData(d['-f'], outfile, d['-r'], d['-maskReps']))
    background = mpc.copy(libctest.getBackground(ds, c_int(2)))
    
    to = multiEval(d, ds, background, pickleFile)

    # return all  the models that have been learned
    return to
