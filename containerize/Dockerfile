ARG BUILDIMAGE
FROM ${BUILDIMAGE} as builder

ARG BUILD_DATE
ARG ANALYSIS_NAME=analysis
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="$ANALYSIS_NAME Docker image" \
      org.label-schema.description="Provides a runnable CMSSW image with $ANALYSIS_NAME pre-installed." \
      org.label-schema.vendor="FNAL"

USER cmsusr
ARG USERDIR_BUILD=/home/${USER}
WORKDIR ${USERDIR_BUILD}

ARG CMSSW_VERSION
ARG TAR

COPY ${TAR} ${USERDIR_BUILD}/${CMSSW_VERSION}.tar.gz
RUN pwd && \
    ls -alh ./ && \
    source /cvmfs/cms.cern.ch/cmsset_default.sh && \
    echo "Unpacking ${CMSSW_VERSION}.tar.gz into ${PWD} ..." && \
    tar -xzf ${CMSSW_VERSION}.tar.gz && \
    rm ${CMSSW_VERSION}.tar.gz && \
    ls -alh ./ && \
    cd ${CMSSW_VERSION}/src/ && \
    scram b ProjectRename && \
    pwd && \
    ls -alh ./ && \
    echo "Setting the CMSSW environment ..." && \
    eval `scramv1 runtime -sh` && \
    echo "The CMSSW_BASE is ${CMSSW_BASE}" && \
    cd ${HOME}

# ---

ARG BASEIMAGE
FROM ${BASEIMAGE}

ARG BUILD_DATE
ARG ANALYSIS_NAME
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="$ANALYSIS_NAME Docker image" \
      org.label-schema.description="Provides a runnable CMSSW image with $ANALYSIS_NAME pre-installed." \
      org.label-schema.vendor="FNAL"

ARG CMSSW_VERSION
ARG NONPRIVILEGED_USER=cmsusr
ARG USERDIR=/home/${NONPRIVILEGED_USER}
WORKDIR ${USERDIR}
COPY --from=builder --chown=cmsusr:cmsusr /home/cmsusr/${CMSSW_VERSION} ${USERDIR}/${CMSSW_VERSION}
RUN pwd && ls -alh ./
