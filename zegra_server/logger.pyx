from .constants cimport LOG_FILE_PATH

cdef class logger:
   async def init_logger():

      # Create a file handler
      file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
      file_handler.setLevel(logging.DEBUG)    # Set the file handler to log all levels

      # Create a console handler
      console_handler = logging.StreamHandler()
      console_handler.setLevel(logging.INFO)  # Set the console handler to log INFO

      # Create a formatter
      formatter = logging.Formatter('[%(asctime)s] [%(levelname).1s] %(funcName)s(): %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

      # Set formatter for both handlers
      file_handler.setFormatter(formatter)
      console_handler.setFormatter(formatter)

      # Add handlers to the root logger
      logging.root.addHandler(file_handler)
      logging.root.addHandler(console_handler)

      # If log file already exists, rename it to 'LOG_FILE_PATH'.old
      if os.path.isfile(LOG_FILE_PATH):
         os.rename(LOG_FILE_PATH, LOG_FILE_PATH + '.old')

         # Set the default logging level to INFO
         logging.root.setLevel(logging.INFO)
