function verify_mat_in_matlab(matfile)
% Verify a NatureMask Studio MAT export with MATLAB's standard LOAD function.
% Usage (from the repo root):
%   matlab -batch "addpath('tests/acoustic_validation'); verify_mat_in_matlab('examples/sample-projects/example5_masker_pascal.mat')"
S = load(matfile);
required = {'sig','fs','t','duration','channels','f_oct','f_third','f_psd','metadata'};
for k = 1:numel(required)
    assert(isfield(S, required{k}), 'missing variable %s', required{k});
end
[N, C] = size(S.sig);
assert(isscalar(S.fs) && S.fs > 0, 'fs must be a positive scalar');
assert(isequal(size(S.t), [N 1]), 't must be N x 1');
assert(abs(S.t(end) - (N-1)/S.fs) < 1e-9, 't inconsistent with fs');
assert(abs(S.duration - N/S.fs) < 1e-9, 'duration inconsistent');
assert(S.channels == C, 'channels inconsistent');
assert(all(isfinite(S.sig(:))), 'non-finite samples');
md = S.metadata;
fprintf('sig: %d x %d (%s), fs = %g Hz, duration = %.2f s\n', N, C, class(S.sig), S.fs, S.duration);
fprintf('signal_domain = %s, calibration_status = %s\n', md.signal_domain, md.calibration_status);
if strcmp(md.calibration_status, 'calibrated')
    assert(isfield(S,'L_Aeq') && isfield(S,'Lp_oct') && isfield(S,'Lp_third'), 'calibrated export must contain SPL fields');
    if strcmp(md.signal_domain, 'pressure_Pa')
        p = mean(S.sig, 2);
        % independent MATLAB check: overall Z-weighted level of the per-channel signals vs exported L_Zeq
        Lz = 10*log10(mean(mean(S.sig.^2, 1)) / (20e-6)^2);
        fprintf('L_Zeq exported = %.2f dB, recomputed in MATLAB = %.2f dB\n', S.L_Zeq, Lz);
        assert(abs(Lz - S.L_Zeq) < 0.5, 'L_Zeq mismatch');
    end
    fprintf('L_Aeq = %.2f dB re 20 uPa; octave bands: %s Hz\n', S.L_Aeq, mat2str(round(S.f_oct'),6));
else
    assert(~isfield(S,'L_Aeq'), 'uncalibrated export must not contain SPL');
end
fprintf('MATLAB_VERIFY_OK\n');
end
