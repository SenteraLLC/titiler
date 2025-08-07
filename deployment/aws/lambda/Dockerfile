FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

# Update pip:
RUN pip install pip -U

# Install system dependencies
RUN dnf install -y \
    tar \
    gzip \
    bzip2 \
    sqlite-devel \
    libtiff-devel \
    git \
    cmake \
    gcc-c++ \
    curl-devel
RUN dnf clean all

# Build PROJ from source
WORKDIR /tmp
RUN curl -L https://download.osgeo.org/proj/proj-9.6.2.tar.gz | tar -xz
RUN mkdir proj-9.6.2/build
WORKDIR /tmp/proj-9.6.2/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=/usr
RUN cmake --build . --target install -j10

# Build GEOS from source
WORKDIR /tmp
RUN curl -L https://download.osgeo.org/geos/geos-3.13.1.tar.bz2 | tar -xj
RUN mkdir geos-3.13.1/build
WORKDIR /tmp/geos-3.13.1/build
RUN cmake \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DBUILD_DOCUMENTATION=OFF \
    -DBUILD_TESTING=OFF \
    ..
RUN make -j10
RUN make install

# Build the latest GDAL from source:
WORKDIR /tmp
RUN git clone https://github.com/OSGeo/gdal.git
RUN mkdir -p gdal/build
WORKDIR /tmp/gdal/build
RUN cmake \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DGDAL_USE_GEOS=ON \
    -DGDAL_USE_CURL=ON \
    -DGDAL_USE_LIBKML=OFF \
    -DGDAL_USE_GRIB=OFF \
    -DBUILD_APPS=OFF \
    -DCMAKE_BUILD_TYPE=MinSizeRel \
    ..
RUN cmake --build . --target install -j10

# Build a rasterio wheel from source, which will make use of our GDAL
# build. The wheel collects up the necessary system libraries for
# eventual bundling into a Lambda artifact.
RUN pip install build auditwheel patchelf
RUN pip wheel rasterio --no-binary rasterio -w /tmp/rasterio-build
RUN auditwheel repair /tmp/rasterio-build/rasterio-*.whl -w /tmp/rasterio-wheel
RUN pip install /tmp/rasterio-wheel/rasterio-*.whl -t /asset

# Build TiTiler from source:
WORKDIR /tmp
COPY . /titiler
RUN pip install \
    # From source to pull in our tile-clipping feature:
    "/titiler/src/titiler/application" \
    # mangum to host the app on AWS Lambda:
    "mangum>=0.10.0" typing_extensions \
    # Build pydantic from source:
    --no-binary pydantic \
    # Bundle the output into /asset:
    -t /asset

# Reduce package size and remove useless files
WORKDIR /asset
RUN find . -type f -name '*.pyc' | while read f; do n=$(echo $f | sed 's/__pycache__\///' | sed 's/.cpython-[0-9]*//'); cp $f $n; done;
RUN find . -type d -a -name '__pycache__' -print0 | xargs -0 rm -rf
RUN find . -type d -a -name 'tests' -print0 | xargs -0 rm -rf
RUN rm -rdf numpy/doc/ boto3* botocore* bin geos_license Misc

# Copy bits into /asset
# NOTE: I *also* found that a couple Lambda environment variables need
#       to be set for all this to work:
#       - GDAL_DATA : "/var/task/gdal"
#       - PROJ_DATA : "/var/task/proj"
WORKDIR /asset
RUN mkdir -p /asset/proj
RUN cp -r /usr/share/proj/* /asset/proj/
RUN mkdir -p /asset/gdal
RUN cp -r /usr/share/gdal/* /asset/gdal/
COPY deployment/aws/lambda/handler.py handler.py

# Ref: https://github.com/developmentseed/titiler/discussions/1108#discussioncomment-13045681
RUN cp /usr/lib64/libexpat.so.1 .

RUN python -c "from handler import handler; print('All Good')"

CMD ["echo", "hello world"]
