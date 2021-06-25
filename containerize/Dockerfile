ARG BUILDIMAGE
FROM ${BUILDIMAGE} as builder

ARG BUILD_DATE
ARG ANALYSIS_NAME=analysis
LABEL   org.label-schema.build-date=$BUILD_DATE \
        org.label-schema.name="$ANALYSIS_NAME Docker image" \
        org.label-schema.description="Provides a runnable CMSSW images with $ANALYSIS_NAME pre-installed." \
        org.label-schema.vendor="FNAL"

USER    cmsusr
WORKDIR /home/cmsusr

ARG CMSSW_VERSION
ARG TAR

COPY ${TAR} /home/cmsusr/${CMSSW_VERSION}.tar.gz
RUN pwd && \
	ls -alh ./ && \
	source /cvmfs/cms.cern.ch/cmsset_default.sh && \
	echo "Unpacking ${CMSSW_VERSION}.tar.gz into ${PWD} ..." && \
	tar -xzf ${CMSSW_VERSION}.tar.gz && \
	ls -alh ./ && \
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
LABEL   org.label-schema.build-date=$BUILD_DATE \
        org.label-schema.name="$ANALYSIS_NAME Docker image" \
        org.label-schema.description="Provides a runnable CMSSW images with $ANALYSIS_NAME pre-installed." \
        org.label-schema.vendor="FNAL"

ARG CMSSW_VERSION
#ARG USERNAME=cmsuser
#COPY --from=builder --chown=${USERNAME}:${USERNAME} /home/cmsusr/${CMSSW_VERSION} /home/${USERNAME}/${CMSSW_VERSION}
COPY --from=builder --chown=cmsusr:cmsusr /home/cmsusr/${CMSSW_VERSION} /home/cmsusr/${CMSSW_VERSION}
WORKDIR /home/cmsusr
RUN pwd && ls -alh ./