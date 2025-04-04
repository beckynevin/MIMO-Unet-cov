import torch
from abc import ABC, abstractmethod

class UncertaintyLoss(torch.nn.Module, ABC):
    def __init__(self) -> None:
        super().__init__()
    
    @abstractmethod
    def forward(self, y_hat, log_variance, y, mask) -> torch.Tensor:
        pass

    @abstractmethod
    def std(self, mu, log_variance) -> torch.Tensor:
        pass

    @abstractmethod
    def mode(self, mu, log_variance) -> torch.Tensor:
        pass

    @abstractmethod
    def calculate_dist_param(self, std: torch.Tensor, *, log: bool = False) -> torch.Tensor:
        pass

    @property
    @abstractmethod
    def num_distribution_params(self) -> int:
        pass

    @classmethod
    def from_name(cls, name: str) -> "UncertaintyLoss":
        if name == "gaussian_nll":
            return GaussianNLL()
        elif name == "cov_gaussian_nll":
            return CovGaussianNLL()
        elif name == "laplace_nll":
            return LaplaceNLL()
        elif name =="cov_laplace_nll":
            return CovLaplaceNLL()
        else:
            raise ValueError(f"Unknown loss function: {name}")


class CovGaussianNLL(UncertaintyLoss):
    num_distribution_params = None  # Adjust as needed

    def __init__(self, eps_min: float = 1e-5):
        """
        Negative log-likelihood for a multivariate Gaussian distribution.

        Args:
            eps_min: Minimum value to add to the diagonal for numerical stability.
        """
        super().__init__()
        self.eps_min = eps_min

    def forward(
        self, 
        y_hat: torch.Tensor,  # Predicted mean (batch_size, d)
        L_flat: torch.Tensor, # Predicted Cholesky factors (batch_size, d * (d + 1) / 2)
        y: torch.Tensor,       # Target values (batch_size, d)
        mask: torch.Tensor = None,
        reduce_mean: bool = True,
    ):
        """
        Computes the multivariate Gaussian negative log-likelihood.
        
        Args:
            y_hat: Predicted mean vector
            L_flat: Flattened lower-triangular Cholesky decomposition of the covariance matrix
            y: Target vector
        Returns:
            Negative log-likelihood loss.
        """
        batch_size, d = y_hat.shape  # Number of samples, dimensionality

        # Reconstruct lower-triangular matrix L from L_flat
        L = torch.zeros(batch_size, d, d, device=y.device)
        tril_indices = torch.tril_indices(row=d, col=d, offset=0)
        L[:, tril_indices[0], tril_indices[1]] = L_flat

        # Ensure L has a small positive diagonal for numerical stability
        L[:, torch.arange(d), torch.arange(d)] += self.eps_min

        # Compute covariance matrix: Sigma = L L^T
        Sigma = L @ L.transpose(-1, -2)  # Ensure positive definiteness

        # Compute (y - y_hat)
        diff = (y - y_hat).unsqueeze(-1)  # Shape (batch_size, d, 1)

        # Solve Lx = diff for x (i.e., compute Sigma^{-1} @ diff efficiently)
        L_inv_diff = torch.linalg.solve_triangular(L, diff, upper=False)
        mahalanobis_term = (L_inv_diff ** 2).sum(dim=1)  # Mahalanobis distance term

        # Compute log determinant: log |Sigma| = 2 * sum(log(diag(L)))
        log_det_Sigma = 2 * torch.sum(torch.log(torch.diagonal(L, dim1=-2, dim2=-1)), dim=-1)

        # Compute final NLL loss
        loss = 0.5 * (log_det_Sigma + mahalanobis_term.squeeze(-1) + d * torch.log(torch.tensor(2 * torch.pi, device=y.device)))

        if mask is not None:
            loss = loss * mask

        if reduce_mean:
            return torch.mean(loss)
        return loss

    def std(self, mu: torch.Tensor, L_flat: torch.Tensor):
        """Compute the standard deviation (diagonal of covariance matrix)."""
        batch_size, d = mu.shape
        L = torch.zeros(batch_size, d, d, device=mu.device)
        tril_indices = torch.tril_indices(row=d, col=d, offset=0)
        L[:, tril_indices[0], tril_indices[1]] = L_flat
        return torch.diagonal(L @ L.transpose(-1, -2), dim1=-2, dim2=-1) ** 0.5

    def mode(self, mu: torch.Tensor, L_flat: torch.Tensor):
        """Mode of a Gaussian distribution is its mean."""
        return mu

    def calculate_dist_param(self, std: torch.Tensor, *, log: bool = False):
        """
        Calculate the distribution parameter based on the provided standard deviation.
        
        Args:
            std: The tensor containing the standard deviation values.
            log: If set to True, return the natural logarithm of the calculated parameter.
        
        Returns:
            A tensor with the calculated distribution parameter.
        """
        param = std ** 2
        param = param.clone()

        with torch.no_grad():
            param.clamp_(min=self.eps_min)

        if log:
            param = torch.log(param)

        return param



class GaussianNLL(UncertaintyLoss):
    num_distribution_params = 2

    def __init__(self, eps_min: float = 1e-5, eps_max: float = 1e3):
        super().__init__()
        self.eps_min = eps_min
        self.eps_max = eps_max

    def forward(
        self, 
        y_hat: torch.tensor, 
        log_variance: torch.tensor, 
        y: torch.tensor,
        *,
        mask: torch.tensor = None,
        reduce_mean: bool = True,
    ):
        """Negative log-likelihood for a Gaussian distribution.
        Adding weight decay yields the negative log posterior.

        Args:
            y_hat: Predicted mean
            log_variance: Predicted log variance
            y: Target
        Returns:
            Negative log-likelihood for a Gaussian distribution
        """
        diff = y_hat - y

        variance = torch.exp(log_variance).clone()
        with torch.no_grad():
            variance.clamp_(min=self.eps_min, max=self.eps_max)
        
        loss = torch.log(variance) + diff ** 2 / variance

        if mask is not None:
            loss = loss * mask

        if reduce_mean:
            return torch.mean(loss)
        return loss


    def std(
        self, 
        mu: torch.Tensor, 
        log_variance: torch.Tensor
    ):
        return torch.exp(log_variance) ** 0.5

    def mode(
        self, 
        mu: torch.Tensor, 
        log_variance: torch.Tensor,
    ):
        return mu
    
    def calculate_dist_param(
        self, 
        std: torch.Tensor,
        *,
        log: bool = False,
    ):
        """
        Calculate the distribution parameter based on the provided standard deviation.

        Args:
            std: The tensor containing the standard deviation values.
            log: If set to True, return the natural logarithm of the calculated parameter.

        Returns:
            A tensor with the calculated distribution parameter.
        """
        param = std ** 2
        param = param.clone()

        with torch.no_grad():
            param.clamp_(min=self.eps_min, max=self.eps_max)

        if log:
            param = torch.log(param)

        return param


class LaplaceNLL(UncertaintyLoss):
    num_distribution_params = 2

    def __init__(self, eps_min: float = 1e-5, eps_max: float = 1e3):
        super().__init__()
        self.eps_min = eps_min
        self.eps_max = eps_max
        
    def forward(
        self, 
        y_hat: torch.Tensor, 
        log_scale: torch.Tensor, 
        y: torch.Tensor,
        *,
        mask: torch.Tensor = None,
        reduce_mean: bool = True,
    ):
        """Negative log-likelihood for a Laplace distribution.
        Adding weight decay yields the negative log posterior.

        Args:
            y_hat: Predicted mean
            log_scale: Predicted log scale
            y: Target
        Returns:
            Negative log-likelihood for a Laplace distribution
        """
        diff = y_hat - y

        scale = torch.exp(log_scale).clone()
        with torch.no_grad():
            scale.clamp_(min=self.eps_min, max=self.eps_max)

        loss = torch.log(scale) + diff.abs() / scale

        if mask is not None:
            loss = loss * mask

        if reduce_mean:
            return torch.mean(loss)
        return loss

    def std(self, mu, log_scale):
        return torch.exp(log_scale) * (2 ** 0.5)

    def mode(self, mu, log_scale):
        return mu
    
    def calculate_dist_param(self, std: torch.Tensor, *, log: bool = False) -> torch.Tensor:
        """
        Calculate the distribution parameter based on the provided standard deviation.

        Args:
            std: The tensor containing the standard deviation values.
            log: If set to True, return the natural logarithm of the calculated parameter.

        Returns:
            A tensor with the calculated distribution parameter.
        """
        param = std / (2 ** 0.5)
        param = param.clone()

        with torch.no_grad():
            param.clamp_(min=self.eps_min, max=self.eps_max)

        if log:
            param = torch.log(param)

        return param


class EvidentialLoss(torch.nn.Module):
    num_distribution_params = 4
    
    def __init__(self, coeff: float) -> None:
        super().__init__()
        self.coeff = coeff

    @staticmethod
    def evidential_loss(mu, v, alpha, beta, targets):
        """
        Code from https://github.com/aamini/chemprop
        
        Use Deep Evidential Regression Sum of Squared Error loss

        :mu: Pred mean parameter for NIG
        :v: Pred lambda parameter for NIG
        :alpha: predicted parameter for NIG
        :beta: Predicted parmaeter for NIG
        :targets: Outputs to predict

        :return: Loss
        """

        # Calculate SOS
        # Calculate gamma terms in front
        def Gamma(x):
            return torch.exp(torch.lgamma(x))

        coeff_denom = 4 * Gamma(alpha) * v * torch.sqrt(beta)

        coeff_num = Gamma(alpha - 0.5)
        coeff = coeff_num / coeff_denom

        # Calculate target dependent loss
        second_term = 2 * beta * (1 + v)
        second_term += (2 * alpha - 1) * v * torch.pow((targets - mu), 2)
        L_SOS = coeff * second_term

        # Calculate regularizer
        L_REG = torch.pow((targets - mu), 2) * (2 * alpha + v)

        loss_val = L_SOS + L_REG

        return loss_val

    def forward(self, evidential_output, y_true, *, mask=None, reduce_mean=False) -> torch.Tensor:
        gamma, v, alpha, beta = torch.unbind(evidential_output, dim=1)
        loss = self.evidential_loss(
            mu=gamma,
            v=v,
            alpha=alpha,
            beta=beta,
            targets=y_true.squeeze(dim=1),
        )

        if mask is not None:
            loss = loss * mask

        if reduce_mean:
            return torch.mean(loss)
        
        return loss
        
    @staticmethod
    def mode(evidential_output):
        gamma, v, alpha, beta = torch.unbind(evidential_output, dim=1)
        return gamma
    
    @staticmethod
    def aleatoric_var(evidential_output):
        gamma, v, alpha, beta = torch.unbind(evidential_output, dim=1)
        return beta / (alpha - 1)
    
    @staticmethod
    def epistemic_var(evidential_output):
        gamma, v, alpha, beta = torch.unbind(evidential_output, dim=1)
        return beta / (v * (alpha - 1))
