# Literature Review: SRH Image Classification

## References

### 1. Egorov, 2025. Siberian radioheliograph image classification using ensemble of CLIP, EfficientNet and CatBoost models

- **File**: [literature/2507.04211v1.pdf](../literature/2507.04211v1.pdf)
- **URL**: https://arxiv.org/abs/2507.04211
- **Key ideas**: Proposes an ensemble model (CLIP + EfficientNet + CatBoost) for binary classification of SRH image quality at 3000 MHz. Training data prepared via zero-shot CLIP labeling with manual validation (10,000 images). Ensemble outperforms individual models with 95% accuracy and 95.8% F1-score.
- **Methodology**: Data preprocessing (normalization, log transformation), CLIP zero-shot labeling, EfficientNet-B0 transfer learning, CatBoost on embeddings, feedforward ensemble. Web service and API deployed for daily classification.
- **Results**: Ensemble accuracy 95%, standalone EfficientNet ~90%. CatBoost variants intermediate. Model deployed at https://forecasting.iszf.irk.ru/srh.

### 2. Lesovoi et al., 2017. Siberian Radioheliograph: first results

- **Key ideas**: First results from the 48-antenna SRH configuration. Instrument characteristics and calibration methodology. Spatial resolution 70'', temporal cadence ~2 min, frequency range 3-24 GHz.
- **Methodology**: Redundancy-based calibration using adjacent and non-adjacent antenna pairs.

### 3. Altyntsev et al., 2020. Multiwave Siberian Radioheliograph

- **Key ideas**: Description of multi-frequency observation mode. SRH operates at 32 frequency channels in 3-24 GHz range. Different channels have different noise statistics, beam sizes, and emission properties.
- **Relevance**: Directly informs why cross-frequency generalization may fail — different frequencies probe different solar atmospheric layers.

### 4. Armstrong & Fletcher, 2019. Fast solar image classification using deep learning

- **Key ideas**: Demonstrated transfer learning effectiveness for solar image classification tasks. Pre-trained CNNs can be adapted to solar data with limited labeled examples.
- **Relevance**: Motivation for using pre-trained models in the ensemble.

### 5. Asensio Ramos et al., 2023. Machine learning in solar physics

- **Key ideas**: Comprehensive review of ML applications in solar physics. Covers transfer learning, CNNs, and challenges of domain adaptation for solar data.

## Gap Analysis

The main paper (Egorov, 2025) trains and evaluates the ensemble model **exclusively on the 3000 MHz channel**. Cross-frequency generalization — applying the 3000 MHz model to 6000 MHz and 12200 MHz data — is not addressed. This is the gap the present study fills.

The SRH literature documents that different frequency channels have substantially different observational characteristics (beam size, noise, emission layers), suggesting that cross-frequency generalization is non-trivial. No previous work has quantified how well a single-channel quality classifier transfers to other frequencies.
