import helpers as hp

the_file = '/Users/manusdonahue/Desktop/Projects/gstudy_converter/testdata/1.3.46.670589.11.17029.5.0.8164.2016041311023902000-301-1-1h7ec6.dcm'
targ_folder = '/Users/manusdonahue/Desktop/Projects/gstudy_converter/conv_testing/'

hp.dicom_to_parrec(the_file, targ_folder)

