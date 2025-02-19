#pragma once

#ifdef USE_ESP32

#include "../i2s_audio.h"

#include "esphome/components/microphone/microphone.h"
#include "esphome/core/component.h"

namespace esphome {
namespace i2s_audio {

class I2SAudioMicrophone : public I2SAudioIn, public microphone::Microphone, public Component {
 public:
  void setup() override;
  void start() override;
  void stop() override;

  void loop() override;

  void set_din_pin(int8_t pin) { this->din_pin_ = pin; }
  void set_pdm(bool pdm) { this->pdm_ = pdm; }

#if SOC_I2S_SUPPORTS_ADC
  void set_adc_channel(adc1_channel_t channel) {
    this->adc_channel_ = channel;
    this->adc_ = true;
  }
#endif

  void set_channel(i2s_channel_fmt_t channel) { this->channel_ = channel; }

 protected:
  void start_();
  void stop_();
  void read_();

  int8_t din_pin_{I2S_PIN_NO_CHANGE};
#if SOC_I2S_SUPPORTS_ADC
  adc1_channel_t adc_channel_{ADC1_CHANNEL_MAX};
  bool adc_{false};
#endif
  bool pdm_{false};
  std::vector<uint8_t> buffer_;
  i2s_channel_fmt_t channel_;

  HighFrequencyLoopRequester high_freq_;
};

}  // namespace i2s_audio
}  // namespace esphome

#endif  // USE_ESP32
